"""Hold-to-trigger commands: a sign (ASL letter or gesture) held still fires its action.

Why "hold": a sign passes through your hand for a few frames whenever you move, so
acting the instant one appears would fire by accident all the time. Requiring it to
be held, and only while the pen is up, keeps commands deliberate.
"""
import config


class HoldTrigger:
    """Feed it the current sign every frame (or None for "no sign").
    It returns the action to run, exactly once per hold, or None."""

    def __init__(self, actions, hold_s=config.COMMAND_HOLD_S, clear_hold_s=config.CLEAR_HOLD_S,
                 repeat_s=config.COMMAND_REPEAT_S):
        self.actions = dict(actions)     # sign -> action string
        self.hold_s, self.clear_hold_s, self.repeat_s = hold_s, clear_hold_s, repeat_s
        self.sign = None                 # the sign currently being held, if it has an action
        self.progress = 0.0              # 0..1: how far through the hold (for the on-screen bar)
        self._since = 0.0
        self._fired_at = None

    def _needed(self, action):
        return self.clear_hold_s if action == "clear" else self.hold_s

    def update(self, sign, now):
        action = self.actions.get(sign)
        if action is None:               # nothing held (or a sign with no action)
            self.sign, self.progress, self._fired_at = None, 0.0, None
            return None
        if sign != self.sign:            # a new sign just started
            self.sign, self._since, self._fired_at = sign, now, None
        if self._fired_at is None:
            held = now - self._since
            self.progress = min(1.0, held / self._needed(action))
            if held >= self._needed(action):
                self._fired_at = now
                return action
        elif action in ("next_color", "prev_color", "next_brush") and now - self._fired_at >= self.repeat_s:
            self._fired_at = now         # stepping actions repeat while the sign is held
            return action
        return None
