# Copyright (c) 2016 Luke San Antonio Bialecki
# All rights reserved.

from datetime import datetime
from enum import Enum

DATE_FMT = '%Y-%m-%d'


# We can't use lowercase pass so just make them capital
class ObjType(Enum):
    User = 1
    Pass = 2


class LiveObj:
    """Represents a pass or a user in a queue (with a request token)."""

    def __init__(self, ty, obj_id, obj_token):
        self.ty = ty
        self.id = obj_id
        self.token = obj_token

    @classmethod
    def fromstring(self, obj_str, ty):
        id, token = tuple(obj_str.split(':'))
        return LiveObj(ty, int(id), int(token))

    def __str__(self):
        return '{}:{}'.format(self.id, self.token)

    def __bytes__(self):
        return str(self).encode()


def date_to_str(day):
    return day.strftime(DATE_FMT)


def str_to_date(s):
    return datetime.strptime(s, DATE_FMT)


def _obj_exists(r, queue, obj):
    """Returns whether the obj exists in the given queue."""
    size = r.llen(queue)

    # No reason to call lrange if we aren't even dealing with a list, for
    # example.
    if size == 0:
        return False

    ###
    # Hopefully this isn't so wildly inefficient that it blows up in our
    # face later.
    ###
    contents = r.lrange(queue, 0, size)

    # Make sure to use bytes so that comparisons work.
    return True if bytes(obj) in contents else False


# The set of patterns include anything that can be used to identify a day
# for example: monday, tuesday, 4 for the fourth of day of every month.

# Rules identify who can park on a matching day and what spot if necessary.
# They include none, indicating parking should not be managed on a given day,
# next to iterate over all states, or an expression that maps spots on a
# particular daystates to other spots.

# Example patterns

# One state for every weekday, parking is not managed by the app on weekends:
# [('monday', 1), ('tuesday', 2), ('wednesday', 3), ('thursday', 4),
#  ('friday', 5), ('saturday', 'none'), ('sunday', 'none')]

# Alternating A day and B days excluding weekends:
# [('monday', 'next'), ('tuesday', 'next'), ('wednesday', 'next'),
# ('thursday', 'next), ('friday', 'next'), ('saturday', 'none'),
# ('sunday', 'none')]

# Or more simply
# [('saturday', 'none'), ('sunday', 'none'), ('*', 'next')]

# Rules are processed by finding the first matching pattern and applying the
# rule or list of rules. Spot is determined from the first matching rule.

# Rule syntax
# 'next' OR
# 'none' OR
# state id (int) OR
# <state_id>:<spot mapping set> (string)

# spot mapping sets are a comma separated list of spot mapping expressions with
# the following syntax (start_spot_num and end_spot_num are inclusive):
# <start_spot_num>([-<end_spot_num>[(<spot_offset>)]]|[=<adjusted_spot_num>)

# Example:
# This maps spots 1-3 to 2-4: 1=2,2=3,3=4. It can also be written: 1-3(1)

# Example:
# On weekdays that are not state 1, allow spots 1-20 (of state 1) to park in
# spots 41-60. On state 1 days, next gives state 1 passs the right to park in
# their regular spot. On state 2 days, the second rule is used.
# This is the rule set:
# [('saturday', 'none'), ('sunday', 'none'), ('*', ['next', '1:1-20(40)'])]

class FixedDaystate:
    def __init__(self, date, state_id):
        self.date = date
        self.state_id = state_id

    @classmethod
    def fromstring(cls, str):
        date, state_id = tuple(str.split(':'))
        return FixedDaystate(datetime.strptime(date, DATE_FMT), int(state_id))

    def __str__(self):
        return self.date.strftime(DATE_FMT) + ':' + str(self.state_id)

    def __eq__(self, other):
        return (self.date.year == other.date.year and
                self.date.month == other.date.month and
                self.date.day == other.date.day and
                self.state_id == other.state_id)

    def __ne(self, other):
        return not self == other


class InvalidFixDate(Exception):
    def __init__(self):
        pass


class LiveOrg:
    """This class manages live org data.

    This stuff _will not_ go into the database anytime soon (in its current
    form). It _will_ be used extensively by our background worker.

    """

    def __init__(self, redis, org_id):
        self.r = redis

        # Can we make this immutable? That way we don't have to call the
        # active_queue_set and friend functions over and over.
        self.org_id = org_id

    ###
    # Names of redis keys
    ###
    def _active_queue_set(self):
        """Returns the name of the active queue set for this org."""
        return str(self.org_id) + ':active-queues-set'

    def _active_queue_temp_set(self):
        return str(self.org_id) + ':active-queues-temp-set'

    def _active_queue_diff_set(self):
        return str(self.org_id) + ':active-queues-diff-set'

    def _active_queue_list(self):
        """Returns the name of the active queue list for this org."""
        return str(self.org_id) + ':active-queues-list'

    def _borrow_queue(self, day):
        """Returns name of a day's borrow queue."""
        return str(self.org_id) + ':' + date_to_str(day) + ':borrow'

    def _lend_queue(self, day):
        """Returns name of a day's lend queue."""
        return str(self.org_id) + ':' + date_to_str(day) + ':lend'

    def _user_token_hash(self):
        """Returns the name of the hash containing user tokens."""
        return str(self.org_id) + ':user-tokens'

    def _pass_token_hash(self):
        """Returns the name of the hash containing pass tokens."""
        return str(self.org_id) + ':pass-tokens'

    def _fixed_daystates_list(self):
        return str(self.org_id) + ':fixed-daystates'

    def _token_hash(self, ty):
        if ty == ObjType.User:
            return self._user_token_hash()
        elif ty == ObjType.Pass:
            return self._pass_token_hash()
        else:
            return None

    ###
    # Functions for a worker
    ###

    def cycle_active_queue(self):
        """Returns a queue that needs to be processed.

        The result is pumped atomically using the redis command RPOPLPUSH, which
        means the queues will eventually repeat but multiple workers can call
        this all at once, etc.

        Returns the string name of a queue.

        """
        return self.r.rpoplpush(
            self._active_queue_list(), self._active_queue_list()
        )

    def reconcile_active_queue(self):
        def find_missing_queues(pipe):
            # Get the contents of the list
            length = self.r.llen(self._active_queue_list())
            contents = self.r.lrange(self._active_queue_list(), 0, length)

            pipe.multi()

            # Clear the temporary set.
            # As long as the list doesn't change we don't need to worry, the set
            # will not have duplicates, etc.
            pipe.delete(self._active_queue_temp_set())

            # Add the contents of the active queue *list* to this temporary set.
            pipe.sadd(self._active_queue_temp_set(), *contents)

            # Check if any elements are in the set but not the list.
            pipe.sdiff(self._active_queue_diff_set(),
                       self._active_queue_set(),
                       self._active_queue_temp_set())

        # Watch the list, if it changes, it's all over. Furthermore, if the set
        # changes, we need to give it time for the list to change too so we
        # don't think its not there when it was going to eventually be there and
        # we just added a queue twice. Honestly this isn't the end of the world,
        # because it will eventually be removed (hopefully).
        num_missing = self.r.transaction(find_missing_queues,
                                         self._active_queue_list(),
                                         self._active_queue_set())[2]

        def add_missing_queues(pipe):
            # Add the elements missing from the list to the list.
            contents = pipe.smembers(self._active_queue_diff_set())

            pipe.multi()
            pipe.lpush(self._active_queue_list(), *contents)
            pipe.execute()

        if num_missing > 0:
            # If members were missing we need to add them!
            self.r.transaction(add_missing_queues,
                               self._active_queue_diff_set(),
                               self._active_queue_set(),
                               self._active_queue_list())

    ###
    # Functions for web service
    ###
    def _activate_day_queue(self, day):
        day_str = date_to_str(day)

        def activate_queue(pipe):
            # Is this queue already active?
            is_member = pipe.sismember(self._active_queue_set(), day_str)

            pipe.multi()
            if is_member == 0:
                # Add the date to the set and list
                pipe.sadd(self._active_queue_set(), day_str)
                pipe.lpush(self._active_queue_list(), day_str)

        self.r.transaction(activate_queue,
                           self._active_queue_set(),
                           self._active_queue_list())

    def _deactivate_day_queue(self, day):
        day_str = date_to_str(day)

        def deactivate_queue(pipe):
            # Is this queue active?
            is_member = pipe.sismember(self._active_queue_set(), day_str)

            pipe.multi()
            if is_member == 1:
                # Remove the date to the set and list
                pipe.srem(self._active_queue_set(), day_str)
                pipe.lrem(self._active_queue_list(), 1, day_str)

        self.r.transaction(deactivate_queue,
                           self._active_queue_set(),
                           self._active_queue_list())

    def obj_token(self, ty, id, r=None):
        """Returns the token of an object given its ID and type.

        It does so by querying into a specific redis set (hash) based on the
        type of the object. If the token doesn't exist, a new token is added."""
        # Possibly use a different redis interface, like a pipeline
        if r is None:
            r = self.r

        # Which hash has our token?
        hash_str = self._token_hash(ty)
        if hash_str is None:
            return None

        # Add a token if it's not already there.
        r.hsetnx(hash_str, str(id), 1)

        # Query the token
        return r.hget(hash_str, str(id))

    def live_obj(self, ty, id, r=None):
        """Returns a live object (with a token) from an ID and type."""
        token = self.obj_token(ty, id, r)
        if token is None:
            # stderr warn?
            return None

        return LiveObj(ty, id, int(token))

    def _refresh_obj_token(self, queue_name, obj_type, obj_id):
        """Updates an object token and moves it to the back of the queue.

        This function is arguably doing more than one thing and therefore isn't
        a very good function, but I ended up coupling the operations so they can
        be done atomically. In that sense, they are very much coupled. Plus, if
        we give this function more information, that means there is less that
        has to be duplicated between refresh_user and refresh_pass, etc. It's
        either that or I just need sleep.

        """

        def refresh_obj(pipe):

            # Get the current user token
            old_token = self.obj_token(obj_type, obj_id, r=pipe)

            # Update the token
            pipe.hincrby(self._token_hash(obj_type), str(obj_id), 1)

            # What's the new object supposed to look like?
            new_obj = self.live_obj(obj_type, obj_id, r=pipe)

            # Get the current state of the queue
            length = pipe.llen(queue_name)
            queue_contents = pipe.lrange(queue_name, 0, length)

            pipe.multi()

            for obj_str in queue_contents:
                # Get the ID and token from the string
                cur_obj = LiveObj.fromstring(obj_str)
                if cur_obj.id == new_obj.id and cur_obj.token != new_obj.token:
                    # The object needs to be updated, because its token doesn't
                    # match the new token we were given.

                    if cur_obj.token != old_token and old_token != None:
                        # We don't recognize this token!
                        # TODO: Add a stderr warning here.
                        pass

                    # Make sure we move them to the back of the queue, if they
                    # refreshed their token it means they should go to the back
                    # of the line.

                    # Remove the object.
                    pipe.lrem(queue_name, 0, obj_str)

                    # Add the obj to the back of the queue with a new token.
                    pipe.lpush(queue_name, bytes(new_obj))

        self.r.transaction(refresh_obj, queue_name)

    def refresh_user(self, date, user_id):
        """Updates a borrow token and moves it to the back of the queue."""
        self._refresh_obj_token(
            self._borrow_queue_str(date), ObjType.User, user_id
        )

    def refresh_pass(self, date, pass_id):
        """Updates a lend token and moves it to the back of the queue."""
        self._refresh_obj_token(
            self._borrow_queue_str(date), ObjType.Pass, pass_id
        )

    def _enqueue_obj(self, queue, obj, check_existing=True):
        """Adds an object to a queue, if it doesn't already exist.

        Returns whether or not the object was enqueued, if this is false it
        means the object was already in the queue, which is fine, it was left
        where it was.
        """

        def enqueue(pipe):
            if check_existing:
                exists = _obj_exists(pipe, queue, obj)
            else:
                exists = False

            if not exists:
                # Add the object to the back of the queue

                ### IMPORTANT ### IMPORTANT ### IMPORTANT
                # The left side of the list is considered the back of the queue.
                # Don't forget to pop from the right with rpop.
                ### IMPORTANT ### IMPORTANT ### IMPORTANT

                pipe.lpush(queue, bytes(obj))

                return True
            return False

        return self.r.transaction(enqueue, queue, value_from_callable=True)

    def _dequeue_obj(self, queue, obj):
        """Removes an object from a queue.

        Returns whether or not the object was removed.
        """

        # TODO: Remove objects with an old token (do this by searching the
        # list and looking at every obj. We could issue a warning if the token
        # is different.
        removed = self.r.lrem(queue, 1, bytes(obj))
        return True if removed > 0 else False

    def enqueue_user_borrow(self, date, user_id):
        # Active the queue if necessary
        self._activate_day_queue(date)
        # Enqueue the user onto the borrow queue
        return self._enqueue_obj(
            self._borrow_queue(date), self.live_obj(ObjType.User, user_id)
        )

    def dequeue_user_borrow(self, date, user_id):
        # TODO: Deactivate the queue if necessary (if it's empty).
        # Dequeue the pass from the borrow queue
        return self._dequeue_obj(
            self._borrow_queue(date), self.live_obj(ObjType.User, user_id)
        )

    def enqueue_pass_lend(self, date, pass_id):
        # Active the queue if necessary
        self._activate_day_queue(date)
        # Enqueue the pass onto the lend queue
        return self._enqueue_obj(
            self._lend_queue(date), self.live_obj(ObjType.Pass, pass_id)
        )

    def dequeue_pass_lend(self, date, pass_id):
        # TODO: Deactivate the queue if necessary (if it's empty).
        # Dequeue the pass from the lend queue
        return self._dequeue_obj(
            self._lend_queue(date), self.live_obj(ObjType.Pass, pass_id)
        )

    def push_fixed_daystate(self, new_fixed_daystate):
        daystate_queue = self._fixed_daystates_list()

        def do_push(pipe):
            # Make sure the new date is more recent then the previous date in
            # the queue. If we go backwards in time, expect issues.

            current_fix = pipe.lindex(daystate_queue, 0)
            if current_fix is not None:
                current_fixed_daystate = FixedDaystate.fromstring(current_fix)
                if new_fixed_daystate.date < current_fixed_daystate.date:
                    # The new fix comes before the one already there.

                    # Either throw an error or adjust the last fix to match
                    # what this fix will effect. This seems unexpected, so just
                    # throw an error for now.
                    raise InvalidFixDate()

            # Start buffered mode because if we are here we are ready to push
            # the new fixed daystate.
            pipe.multi()
            pipe.lpush(daystate_queue, str(new_fixed_daystate))

        self.r.transaction(do_push, daystate_queue)
