# model/window.py

"""
SlidingFrontierWindow maintains a bounded set of consistent cuts (frontiers)
over a partially ordered event stream. New events generate candidate frontiers
via `extend`, which are then processed before being committed and pruned.

Pruning mechanisms can remove dominated or redundant frontiers based on
process coverage and maximality, and ultimately cap the set by recency
or other criteria.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Dict

# Uses the custom logger utility.
from utils.logger import get_logger
from .frontier import Frontier
from .event import Event

logger = get_logger(__name__)


@dataclass(slots=True)
class SlidingFrontierWindow:
    """
    Manages a sliding window of relevant frontiers (consistent cuts).

    A frontier represents a snapshot of the system state consistent with
    the partial order of events. This window dynamically updates these
    frontiers as new events arrive and prunes them to maintain a manageable size.

    Attributes:
      max_size: Maximum number of frontiers to retain after pruning.
      frontiers: Currently stored frontiers, typically ordered to reflect processing or recency.
    """
    max_size: int = 10
    frontiers: List[Frontier] = field(default_factory=list)

    # Internal state for optimized pruning and performance tracking.
    _optimized_pruning_active: bool = False
    _all_system_processes: Set[str] = field(default_factory=set)
    _frontier_outgoing_processes: Dict[Frontier, Set[str]] = field(default_factory=dict)
    _size_warnings_enabled: bool = True
    _peak_size_seen: int = 0

    def __post_init__(self):
        """
        Initializes the window. The window can start empty, with the expectation
        that an initial system frontier (representing the system's starting state)
        will be inserted externally (e.g., by a monitoring component) using
        methods like `insert()` or `clear_and_insert()`.
        """
        # The window starts empty by default.
        # External components are responsible for seeding it with an initial state.
        pass

    def activate_optimized_pruning(self, all_processes: Set[str]) -> None:
        """
        Activates an optimized pruning strategy based on process coverage.

        This pruning helps remove frontiers that are no longer relevant because
        all participating system processes have progressed beyond them.

        Args:
            all_processes: A set of all known process names in the system,
                           excluding any internal or pseudo-processes.
        """
        self._optimized_pruning_active = True
        # Filter out any processes starting with '_' as they might be internal.
        self._all_system_processes = {p for p in all_processes if not p.startswith("_")}
        self._frontier_outgoing_processes.clear()
        for fr in self.frontiers:
            if fr.events:  # Ensure frontier is not representing an empty state.
                self._frontier_outgoing_processes[fr] = set()

    def set_max_size(self, new_max_size: int) -> None:
        """
        Updates the maximum number of frontiers the window should retain.
        If the new size is smaller and the current size exceeds it,
        pruning is triggered immediately.

        Args:
            new_max_size: The new maximum window size.
        """
        old_max_size = self.max_size
        self.max_size = new_max_size
        if new_max_size < old_max_size and len(self.frontiers) > new_max_size:
            logger.info(f"Window max_size reduced from {old_max_size} to {new_max_size}, "
                        f"immediately pruning {len(self.frontiers)} frontiers.")
            self.prune()

    def extend(self, ev: Event) -> List[Frontier]:
        """
        Generates candidate frontiers by extending current frontiers with a new event.

        Each existing frontier in the window is extended by incorporating the
        new event `ev`. If the window is empty (e.g., at initialization),
        the new event itself defines the basis for the first candidate frontier(s).
        Commutativity with other stored frontiers is also considered to generate
        a comprehensive set of potential next states.

        Args:
            ev: The new event to extend the frontiers with.

        Returns:
            A list of unique candidate frontiers.
        """
        if not self.frontiers:
            # If the window is empty, the new event forms the first frontier.
            # This scenario assumes the monitor will handle the initial state.
            initial_candidate_events = {proc: ev for proc in ev.processes}
            return [Frontier(initial_candidate_events)]

        # Use the current set of unique frontiers as seeds for extension.
        unique_seeds: List[Frontier] = list(self.frontiers)

        candidates: Set[Frontier] = set()
        for base_fr in unique_seeds:
            new_fr = base_fr.extend(ev)
            candidates.add(new_fr)

            # If optimized pruning is active, track processes involved in this event
            # relative to the base frontier.
            if self._optimized_pruning_active and base_fr in self._frontier_outgoing_processes:
                observed_system_procs = ev.processes & self._all_system_processes
                self._frontier_outgoing_processes[base_fr].update(observed_system_procs)

            # Consider commutativity: if the new event could have occurred
            # concurrently with events leading to other stored frontiers,
            # extend those other frontiers as well.
            for other_stored_fr in unique_seeds:
                if other_stored_fr is base_fr:
                    continue
                # A new_fr results from base_fr + ev.
                # If other_stored_fr is concurrent with new_fr, it means ev
                # could also have extended other_stored_fr.
                if other_stored_fr.concurrent(new_fr):
                    commuted_fr = other_stored_fr.extend(ev)
                    candidates.add(commuted_fr)
                    if self._optimized_pruning_active and other_stored_fr in self._frontier_outgoing_processes:
                        observed_system_procs_alt = ev.processes & self._all_system_processes
                        self._frontier_outgoing_processes[other_stored_fr].update(observed_system_procs_alt)

        return list(candidates)

    def commit_and_prune_candidates(self, candidates: List[Frontier]) -> None:
        """
        Adds a list of candidate frontiers to the window and then prunes.

        Duplicate frontiers (based on `Frontier.__eq__`) are avoided.
        After adding, the pruning mechanism is triggered.

        Args:
            candidates: A list of candidate frontiers to add.
        """
        for fr in candidates:
            # Check if an equivalent frontier already exists to avoid duplicates.
            is_present = any(existing_fr == fr for existing_fr in self.frontiers)
            if not is_present:
                self.frontiers.append(fr)

            # Initialize tracking for optimized pruning if active.
            if self._optimized_pruning_active and fr.events and fr not in self._frontier_outgoing_processes:
                self._frontier_outgoing_processes[fr] = set()
        self.prune()

    def insert(self, fr: Frontier) -> None:
        """
        Directly inserts a single frontier into the window and then prunes.
        Useful for adding an initial system state or a manually constructed frontier.

        Args:
            fr: The frontier to insert.
        """
        # Initialize tracking for optimized pruning if active.
        if self._optimized_pruning_active and fr.events and fr not in self._frontier_outgoing_processes:
            self._frontier_outgoing_processes[fr] = set()

        # Check if an equivalent frontier already exists.
        is_present = any(existing_fr == fr for existing_fr in self.frontiers)
        if not is_present:
            self.frontiers.append(fr)
        self.prune()

    def clear_and_insert(self, fr: Frontier) -> None:
        """
        Clears all existing frontiers and inserts the given one, then prunes.
        This is typically used to reset the window to a new initial state.

        Args:
            fr: The frontier to insert after clearing.
        """
        self.frontiers.clear()
        self._frontier_outgoing_processes.clear()  # Reset for Rs-pruning.
        self._peak_size_seen = 0
        self.insert(fr)  # `insert` will also call `prune`.

    def prune(self) -> None:
        """
        Applies various pruning strategies to reduce the number of stored frontiers.

        Strategies include:
        1. De-duplication (ensuring unique frontiers).
        2. Rs-pruning (optimized, removes frontiers fully covered by subsequent events).
        3. Maximality pruning (removes frontiers causally preceded by others).
        4. Size capping (truncates to `max_size` if exceeded).
        """
        # 1. De-duplicate frontiers based on their hash and equality.
        unique_list: List[Frontier] = []
        seen_hashes: Set[int] = set()
        for fr_item in self.frontiers:
            h = hash(fr_item)
            if h not in seen_hashes:
                unique_list.append(fr_item)
                seen_hashes.add(h)
        self.frontiers = unique_list

        # 2. Rs-pruning (Optimized Pruning):
        # Removes frontiers if all their system processes have seen subsequent events.
        if self._optimized_pruning_active and self._all_system_processes:
            retained_for_rs: List[Frontier] = []
            for fr_item in self.frontiers:
                # A frontier is redundant if all its relevant system processes
                # have subsequent events recorded.
                if not self._all_system_processes.issubset(self._frontier_outgoing_processes.get(fr_item, set())):
                    retained_for_rs.append(fr_item)
            self.frontiers = retained_for_rs

        # 3. Maximality Pruning:
        # Keep only "maximal" frontiers (those not causally preceded by another in the set).
        if len(self.frontiers) > 1:
            maximals: List[Frontier] = []
            # Heuristic pre-sort to potentially improve comparison order,
            # e.g., by vector clock sum.
            self.frontiers.sort(key=lambda f: sum(f.vc.clock.values()), reverse=True)

            for i, f1 in enumerate(self.frontiers):
                is_maximal_f1 = True
                for j, f2 in enumerate(self.frontiers):
                    if i == j:
                        continue
                    if f1 < f2:  # True if f1 is strictly causally before f2.
                        is_maximal_f1 = False
                        break
                if is_maximal_f1:
                    # Avoid adding structurally identical maximals.
                    if not any(m_fr == f1 for m_fr in maximals):
                        maximals.append(f1)
            self.frontiers = maximals

        # 4. Size Capping:
        # If the number of frontiers exceeds max_size, truncate.
        pre_size_cap_count = len(self.frontiers)
        if len(self.frontiers) > self.max_size:
            if self._size_warnings_enabled:
                logger.warning(f"SlidingFrontierWindow size cap reached: "
                               f"{pre_size_cap_count} frontiers truncated to {self.max_size}.")
            # Keep the most "recent" or highest-priority frontiers.
            # Assuming current list order is newest at end after sorting/additions.
            self.frontiers = self.frontiers[-self.max_size:]

        # Update performance tracking.
        if pre_size_cap_count > self._peak_size_seen:
            self._peak_size_seen = pre_size_cap_count
            if self._size_warnings_enabled and pre_size_cap_count > self.max_size * 0.8:  # Warn if approaching limit.
                logger.info(f"SlidingFrontierWindow approaching size limit: "
                            f"peak {self._peak_size_seen} frontiers (limit: {self.max_size})")

        # Clean up tracking for frontiers that were pruned.
        self._cleanup_frontier_outgoing_processes()

    def _cleanup_frontier_outgoing_processes(self) -> None:
        """Removes entries from _frontier_outgoing_processes for frontiers no longer in the window."""
        if not self._optimized_pruning_active:
            return
        current_frontiers_set = set(self.frontiers)
        # Iterate over a copy of keys for safe deletion.
        for fr_to_check in list(self._frontier_outgoing_processes.keys()):
            if fr_to_check not in current_frontiers_set:
                del self._frontier_outgoing_processes[fr_to_check]

    def get_performance_stats(self) -> Dict[str, int | bool]:
        """
        Returns a dictionary of performance-related statistics for the window.

        Returns:
            A dictionary containing metrics like current size, peak size, etc.
        """
        return {
            'current_size': len(self.frontiers),
            'max_size_limit': self.max_size,
            'peak_size_seen': self._peak_size_seen,
            'utilization_percent': int((len(self.frontiers) / self.max_size) * 100) if self.max_size > 0 else 0,
            'rs_pruning_active': self._optimized_pruning_active,
            'tracked_processes_for_rs': len(self._all_system_processes) if self._optimized_pruning_active else 0
        }

    def enable_size_warnings(self, enabled: bool = True) -> None:
        """
        Enables or disables warning messages related to window size capping.

        Args:
            enabled: True to enable warnings, False to disable.
        """
        self._size_warnings_enabled = enabled

    @property
    def latest(self) -> Frontier | None:
        """
        Returns the most recently added/processed frontier, if any.
        Assumes frontiers are appended to the end of the list.
        """
        return self.frontiers[-1] if self.frontiers else None

    def __iter__(self):
        """Allows iteration over the frontiers in the window."""
        return iter(self.frontiers)

    def __len__(self) -> int:
        """Returns the current number of frontiers in the window."""
        return len(self.frontiers)

    def __bool__(self) -> bool:
        """Returns True if the window contains any frontiers, False otherwise."""
        return bool(self.frontiers)

    def clear(self) -> None:
        """Removes all frontiers from the window and resets peak size tracking."""
        self.frontiers.clear()
        self._peak_size_seen = 0
        if self._optimized_pruning_active:
            self._frontier_outgoing_processes.clear()