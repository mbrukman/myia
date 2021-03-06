"""Misc utilities for inference."""


from contextvars import ContextVar

from ..dtype import Problem
from ..utils import Named, Event, Partializable, eprint


infer_trace = ContextVar('infer_trace')
infer_trace.set({})


# Represents an unknown value
ANYTHING = Named('ANYTHING')

# Represents inference problems
VOID = Named('VOID')

# Represents specialization problems
DEAD = Named('DEAD')
POLY = Named('POLY')
INACCESSIBLE = Named('INACCESSIBLE')


class Unspecializable(Exception):
    """Raised when it is impossible to specialize an inferrer."""

    def __init__(self, problem):
        """Initialize Unspecializable."""
        problem = Problem[problem]
        super().__init__(problem)
        self.problem = problem


class InferenceError(Exception, Partializable):
    """Inference error in a Myia program.

    Attributes:
        message: The error message.
        refs: A list of references which are involved in the error,
            e.g. because they have the wrong type or don't match
            each other.
        traceback_refs: A map from a context to the first reference in
            that context that fails to resolve because of this error.
            This represents a traceback of sorts.

    """

    def __init__(self, message, refs=[], app=None):
        """Initialize an InferenceError."""
        super().__init__(message, refs)
        self.message = message
        self.refs = refs
        self.traceback_refs = infer_trace.get()
        if app is not None:
            self.traceback_refs[app.context] = app

    def print_tb_end(self, fn_ctx, args_ctx, is_prim):
        """Print the error message at the end of a traceback."""
        eprint(f'{type(self).__qualname__}: {self.message}')


class MyiaTypeError(InferenceError):
    """Type error in a Myia program."""

    def print_tb_end(self, fn_ctx, args_ctx, is_prim):
        """Print the error message at the end of a traceback."""
        if fn_ctx is None:
            super().print_tb_end(fn_ctx, args_ctx, is_prim)
            return
        s = f'{type(self).__qualname__}: `{fn_ctx}` cannot be called with' \
            f' argument types {args_ctx}.'
        if is_prim:
            s += f' Reason: {self.message}'
        eprint(s)


class MyiaShapeError(InferenceError):
    """Shape error in a Myia program."""


class ValueWrapper:
    """Wrapper for an inferred value.

    Values may be wrapped using subclasses of ValueWrapper, associating them
    with tracking data or metadata.
    """

    def __init__(self, value):
        """Initialize a ValueWrapper."""
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return type(other) is type(self) \
            and self.value == other.value


class DynamicMap:
    """Represents a sort of mapping that's constantly updated."""

    def __init__(self):
        """Initialize a DynamicMap."""
        self.cache = {}
        self.on_result = Event(
            name='on_result',
            history=self.cache.items
        )

    def provably_equivalent(self, other):
        """Whether this map is provably equivalent to the other."""
        return self is other  # pragma: no cover

    def merge(self, other):
        """Merge the caches of two DynamicMaps.

        This assumes that provably_equivalent is True.
        """
        self.cache.update(other.cache)
        other.cache = self.cache

    async def __call__(self, *args):
        """Infer a property of the operation on the given arguments.

        The results of this call are cached.
        """
        if args not in self.cache:
            res = await self.infer(*args)
            self.cache[args] = res
            self.on_result(args, res)
        return self.cache[args]

    def infer(self, *args):
        """Infer a property of the operation on the given arguments.

        This must be overriden in subclasses.
        """
        raise NotImplementedError()  # pragma: no cover


def unwrap(x):
    """Extract the value if x is a ValueWrapper, return x otherwise."""
    if isinstance(x, ValueWrapper):
        x = x.value
    return x
