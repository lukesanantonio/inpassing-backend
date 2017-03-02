# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

# Take a list of states and after each period (likely to be a single day) go to
# the next state, looping around to the beginning, if necessary. When the org
# wants to override this choice, they go right ahead and fix the index on a
# day, for it to continue from thereafter.

# Figure out the state based on what the last fixed index was and the number of
# periods since it was fixed.

def current_state(states, fixed_index, periods_since_fixed):
    # Given a list of states, the fixed state and the distance since it was
    # fixed, find the current state. This is done by simply rotating
    return states[(fixed_index + periods_since_fixed) % len(states)]
