"""Minimal Result type for use cases that express expected, safe failures.

Expected failures (policy denial, validation) are values, not exceptions;
unexpected failures still raise so they are never silently swallowed
(agent.md change discipline: never convert exceptions to empty successes).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Success[T]:
    value: T

    @property
    def ok(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Failure[E]:
    error: E

    @property
    def ok(self) -> bool:
        return False


def Ok[T](value: T) -> Success[T]:
    return Success(value)


def Err[E](error: E) -> Failure[E]:
    return Failure(error)


type Result[T, E] = Success[T] | Failure[E]
