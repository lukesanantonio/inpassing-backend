# Copyright (c) 2017 Luke San Antonio Bialecki
# All rights reserved.

from collections import namedtuple
from enum import Enum
import msgpack

import pyparsing as pp

from . import str_to_date

# A rule set is a three-element tuple. The first element is a string pattern
# that can match a particular day of the week or month. The second element
# is boolean indicating whether the daystate sequence should be moved forward
# on the particular day. The third element is a list of strings containing rules
# which is detailed below.

# Rules identify who can park on a matching day, sometimes they remap spots of
# a particular daystate to other spots on other daystates.

# Who can park on what day is determined by looking at the last fixed daystate
# and going forward using the rules defined in a bucket. Every time a new
# daystate is fixed, a new bucket is created with new rules being added to the
# most recent bucket.

# Example patterns

# One state for every weekday, parking is not managed by the app on weekends:
# [('monday', false, [1]), ('tuesday', false, [2]),
# ('wednesday', false, [3]), ('thursday', false, [4]),
# ('friday', false, [5])]

# Parking could be disabled on one particular day by pushing the following rule
# onto the current rule bucket ('3-15-17', false, ['none']). March 15th will be
# skipped and the daystates will continue like nothing happened, because the
# above rules take over on every other day.

# Alternating A day and B days excluding weekends:
# [('monday', true, 'cur'), ('tuesday', true, 'cur'),
# ('wednesday', true, 'cur'), ('thursday', true, 'cur'),
# ('friday', true, 'cur')]

# Or more simply
# [('saturday', false, 'none'), ('sunday', false, 'none'), ('*', true, 'cur')]

# In this case, Weekends will match first and bail out while weekdays will look
# to the end, etc.

# Rules are processed by finding the first matching pattern and applying the
# rule or list of rules. Spot is determined from the first matching rule.

# Rule syntax
# 'cur' - The current daystate in the sequence (all spots or nothing deal) OR
# 'none' - Any and all passes are rejected OR
# state id (int) OR
# <state_id>:<spot mapping set> (string)

# spot mapping sets are a comma separated list of spot mapping expressions with
# the following syntax (start_spot_num and end_spot_num are inclusive):
# <start_spot_num>([-<end_spot_num>[(<spot_offset>)]]|[=<adjusted_spot_num>)

# Example:
# This maps spots 1-3 to 2-4: 1=2,2=3,3=4. It can also be written: 1-3(1)

# Example:
# On weekdays that are not state 1, allow spots 1-20 (of state 1) to park in
# spots 41-60. On state 1 days, 'cur' gives state 1 passes the right to park in
# their regular spot while the third rule allows spots 1-20 (of state 2) to
# park, etc.

# This is the rule set:
# [('saturday', false, 'none'),
#  ('sunday', false, 'none'),
#  ('*', true, ['cur', '1:1-20(40)', '2:1-20(40)'])]

# Parse integers as numbers not strings
integer = pp.Word(pp.nums).setParseAction(lambda toks: int(toks[0]))

spot_offset = pp.Literal('(') + integer('spot_offset') + ')'
spot_assignment = pp.Literal('=') + integer('spot_assignment')

# A mapping from a range or spots.
spot_map = integer('start_spot_num') + \
               (pp.Optional(pp.Literal('-') + integer('end_spot_num') +
                            pp.Optional(spot_offset)) ^
                pp.Optional(spot_offset ^ spot_assignment))

# results[0] is the state id
# results[1:] are parse results of each spot map
mapping_syntax = integer('state_id') + \
              pp.Optional(pp.Suppress(':') + pp.Group(spot_map) +
                          pp.ZeroOrMore(pp.Suppress(',') +
                                        pp.Group(spot_map))) ^ \
              'none' ^ 'cur'


class SpotAdjustmentType(Enum):
    Fixed = 1
    Offset = 2


class SpotMap:
    def __init__(self, start, end=None, value=0,
                 adjust_type=SpotAdjustmentType.Offset):
        self.start = start
        self.end = end or start
        self.value = value
        self.adjust_type = adjust_type

        if self.start != self.end:
            assert(self.adjust_type != SpotAdjustmentType.Fixed)

    def includes_spot_num(self, spot_num):
        """Returns whether the given spot would be remapped"""
        return self.start <= spot_num <= self.end

    def adjust_spot_num(self, spot_num):
        if not self.includes_spot_num(spot_num):
            return None

        if self.adjust_type == SpotAdjustmentType.Offset:
            return spot_num + self.value

        elif self.adjust_type == SpotAdjustmentType.Fixed:
            assert(self.start == self.end)
            return self.value

    def __str__(self):
        if self.adjust_type == SpotAdjustmentType.Offset:
            if self.value == 0:
                if self.start == self.end:
                    return str(self.start)
                else:
                    return '{}-{}'.format(self.start, self.end)
            else:
                if self.start == self.end:
                    return '{}({})'.format(self.start, self.value)
                else:
                    return '{}-{}({})'.format(self.start, self.end, self.value)

        elif self.adjust_type == SpotAdjustmentType.Fixed:
            if self.start == self.end:
                return '{}={}'.format(self.start, self.value)

        raise RuntimeError('Unable to __str__ify an invalid rule')

    @classmethod
    def fromdict(cls, dict):
        if 'spot_assignment' in dict:
            # Only use fixed mode if we were given an adjusted spot num.
            return SpotMap(dict['start_spot_num'], dict.get('end_spot_num'),
                           dict['spot_assignment'], SpotAdjustmentType.Fixed)
        else:
            # Use spot offset if it's there, but zero will work if it's missing
            return SpotMap(dict['start_spot_num'], dict.get('end_spot_num'),
                           dict.get('spot_offset', 0), SpotAdjustmentType.Offset)

    @classmethod
    def fromstring(cls, instring):
        return SpotMap.fromdict(
            spot_map.parseString(instring).asDict()
        )


# Mappings are used to figure out who can park and where. A return value of
# False from includes_pass means the mapping isn't relevant. A return value of
# None from adjust_pass means the user cannot park, but if that particular pass
# wasn't really relevant to the mapping, this just means we need to move on.

class CustomMapping:
    """Stores a state and a list of spot mappings."""

    def __init__(self, state_id, mappings=None):
        self.state_id = state_id
        self.spot_mappings = mappings or []

    def includes_pass(self, state_id, spot_num):
        if self.state_id != state_id:
            return False

        if len(self.spot_mappings) == 0:
            return True

        for spot_map in self.spot_mappings:
            if spot_map.includes_spot_num(spot_num):
                return True

        return False

    def adjust_pass(self, state_id, spot_num):
        if not self.includes_pass(state_id, spot_num):
            return None

        if len(self.spot_mappings) == 0:
            return spot_num

        for spot_mapping in self.spot_mappings:
            ret = spot_mapping.adjust_spot_num(spot_num)
            if ret is not None:
                return ret

        return None

    def __str__(self):
        return '{}:{}'.format(
            self.state_id,
            ','.join([str(mapping) for mapping in self.spot_mappings])
        )


class CurStateMapping:
    def __init__(self):
        self.current_state_id = None

    def includes_pass(self, state_id, spot_num):
        if self.current_state_id != state_id:
            return False
        return True

    def adjust_pass(self, state_id, spot_num):
        if not self.includes_pass(state_id, spot_num):
            return None

        return spot_num

    def __str__(self):
        return 'cur'


class NoneMapping:
    def includes_pass(self, state_id, spot_num):
        return True

    def adjust_pass(self, state_id, spot_num):
        return None

    def __str__(self):
        return 'none'


def parse_rule(instring):
    parse_res = mapping_syntax.parseString(instring)

    if 'state_id' in parse_res.asDict():
        mappings = []
        for mapping_res in parse_res[1:]:
            mappings.append(SpotMap.fromdict(mapping_res))
        return CustomMapping(parse_res['state_id'], mappings)
    elif parse_res[0] == 'cur':
        return CurStateMapping()
    elif parse_res[0] == 'none':
        return NoneMapping()
    else:
        raise RuntimeError("Invalid rule string: '{}'".format(instring))


class CompositeMapping:
    """Handles mapping logic when using many mappings."""
    def __init__(self, maps):
        self.maps = maps

    def includes_pass(self, state_id, spot_num):
        for mapping in self.maps:
            if mapping.includes_pass(state_id, spot_num):
                return True
        return False

    def adjust_pass(self, state_id, spot_num):
        for mapping in self.maps:
            if mapping.includes_pass(state_id, spot_num):
                return mapping.adjust_spot_num(state_id, spot_num)
        return None

RuleSet = namedtuple('RuleSet', ['pattern', 'incrday', 'rules', 'timestamp'])

days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
        'sunday']

def dict_from_ruleset(rs):
    rules = []
    if isinstance(rs.rules, CompositeMapping):
        # A composite mapping
        rules = rs.rules.maps
    elif not isinstance(rs.rules, list):
        # One rule, hopefully a string or something the client will
        # understand and that can be directly serialized to JSON.
        rules = [rs.rules]
    else:
        # A regular list of strings, or mappings that we can easier convert
        # to a string.
        rules = rs.rules

    return {
        'pattern': rs.pattern,
        'incrday': rs.incrday,
        'rules': [str(rule) for rule in rules],
        'timestamp': rs.timestamp,
    }


def ruleset_from_dict(d, ts=None):
    d_ts = None
    if 'timestamp' in d:
        d_ts = d.timestamp

    return RuleSet(
        d.pattern, d.incrday, [parse_rule(rule) for rule in d.rules],
        ts or d_ts,
    )


def pattern_matches_date(pattern, date):
    if pattern == '*':
        return True

    if pattern in days:
        pattern_day = days.index(pattern)
        if pattern_day == date.weekday():
            # The date is on the same weekday as the pattern designates
            return True
        else:
            return False
    else:
        try:
            test_date = str_to_date(pattern)
            if (test_date.year == date.year and test_date.month == date.month
                and test_date.day == date.day):
                return True
        except ValueError:
            pass

        return False


def pattern_reoccurs(day):
    if day == '*':
        return True
    return True if day in days else False


def convert_rules(self, res):
    """Converts a list of rule msgpack strings to a list of objects."""
    ret = []
    for rule_set in res:
        # Parse object with string rules
        rs = RuleSet(*msgpack.unpackb(rule_set, encoding='utf-8'))

        # Convert rules to objects
        new_rules = []
        for rule in rs.rules:
            new_rules.append(parse_rule(rule))

        # Add the rule set with the fixed rules to the list we will return.
        ret.append(rs._replace(rules=new_rules))
    return ret
