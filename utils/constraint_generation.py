import numpy as np

from utils.utils import general_sum, general_cat, general_l2norm, epsilon_constant, powerset, \
    sample_at_least_one_of_each


def sample_constraints(constraint_type, **params):
    if constraint_type == 'random_const':
        constraints = sample_offset_constraints_numpy(request_offset_const=False, **params)
    elif constraint_type == 'set_covering':
        constraints = get_set_covering_constraints_numpy(**params)
    else:
        raise NotImplementedError
    return constraints


def get_set_covering_constraints_numpy(num_variables, num_constraints, variable_range, max_subset_size, seed):
    np.random.seed(seed)
    assert variable_range == dict(lb=0.0, ub=1.0)
    assert max_subset_size <= num_constraints

    universe = [i for i in range(num_constraints)]
    subsets = list(powerset(universe))  # remove empty and full set from powerset
    rel_subsets = list(filter(lambda subset: len(subset) <= max_subset_size, subsets[1:]))
    print(f'Num relevant subsets: {len(rel_subsets)}')
    assert num_variables <= len(rel_subsets)

    chosen_subsets = sample_at_least_one_of_each(subsets=rel_subsets, num_classes=num_constraints,
                                                 num_samples=num_variables)

    A = np.zeros((num_constraints, num_variables))
    for subset_idx, subset in enumerate(chosen_subsets):
        for elem in subset:
            A[elem, subset_idx] = -1
    b = np.ones(num_constraints)
    constraints = np.concatenate([A, b[:, None]], axis=1)
    return constraints


def sample_offset_constraints_numpy(num_variables, num_constraints, variable_range, offset_sample_point="random_unif",
                                    request_offset_const=False, feasible_point=None, seed=None):
    """
    Sample constraints represented as A and b, but with individual offset origins
    """
    np.random.seed(seed)

    constraints_in_offset_system = sample_Ab_constraints_numpy(num_variables=num_variables,
                                                               num_constraints=num_constraints)
    offsets = get_hypercube_point_numpy(shape=(num_constraints, num_variables),
                                        point=offset_sample_point, **variable_range)

    constraints_in_base_system = compute_constraints_in_base_coordinate_system(
        constraints_in_offset_system=constraints_in_offset_system, offsets=offsets)

    if feasible_point is not None:
        feasibility_indicator = check_feasibility_numpy(constraints=constraints_in_base_system,
                                                        feasible_point=feasible_point,
                                                        variable_range=variable_range)
        constraints_in_offset_system = constraints_in_offset_system * feasibility_indicator[:, None]

    if request_offset_const:
        return constraints_in_offset_system, offsets
    else:
        constraints = compute_constraints_in_base_coordinate_system(
            constraints_in_offset_system=constraints_in_offset_system, offsets=offsets)
        return constraints


def sample_Ab_constraints_numpy(num_variables, num_constraints, b_value=0.2):
    b = np.ones(shape=[num_constraints]) * b_value
    A = np.random.rand(num_constraints, num_variables) - 0.5
    A_normalized = A / (np.linalg.norm(A, axis=1, keepdims=True) + epsilon_constant)
    constraints = general_cat([A_normalized, b[..., None]], axis=-1)
    return constraints


def get_hypercube_point_numpy(point, shape, lb, ub, scale_sample_range=0.5):
    if point == 'center_hypercube':
        mean = (lb + ub) / 2
        return np.ones(shape) * mean
    elif point == 'origin':
        return np.zeros(shape)
    elif point == 'random_corner':
        rand_zero_ones = np.random.randint(2, size=shape)
        corner = lb * (1 - rand_zero_ones) + ub * rand_zero_ones
        return corner
    elif point == 'random_unif':
        mean = (lb + ub) / 2
        diff = ub - lb
        lb = mean - scale_sample_range * diff / 2
        ub = mean + scale_sample_range * diff / 2
        return np.random.rand(*shape) * (ub - lb) + lb
    else:
        raise NotImplementedError(f'Point {point} not implemented.')


def check_feasibility_numpy(constraints, feasible_point, variable_range):
    num_variables = constraints.shape[-1] - 1
    decision_point = get_hypercube_point_numpy(point=feasible_point, shape=[num_variables], **variable_range)

    # return vector of 1s and -1s, depending on whether the constraint is feasible at the decision point or not
    constraint_eq_solution = np.sum(constraints[:, :-1] * decision_point[None, :], axis=1) + constraints[:, -1]
    is_feasible = (constraint_eq_solution <= 0.0).astype(float)
    feasibility_indicator = 2.0 * is_feasible - 1.0
    return feasibility_indicator


def compute_normalized_constraints(constraints):
    A = constraints[..., :-1]
    norm = general_l2norm(A, axis=-1, keepdims=True)
    constraints = constraints / (norm + epsilon_constant)
    return constraints


def compute_constraints_in_base_coordinate_system(constraints_in_offset_system, offsets):
    # offset is defined as the offset of the offset constraint coordinate system wrt to the base coordinate system
    # origin_offset_const = origin_base + offset
    A, b = constraints_in_offset_system[..., :-1], constraints_in_offset_system[..., -1]
    b_prime = b - general_sum(A * offsets, axis=-1)
    constraints_in_base_system = general_cat([A, b_prime[..., None]], axis=-1)
    return constraints_in_base_system
