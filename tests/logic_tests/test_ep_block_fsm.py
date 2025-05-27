
# test/logic_tests/test_ep_block_fsm.py

import pytest
from logic.ep_block_fsm import EPBlockFSM, Verdict
from parser import parse_and_dlnf
from model.event import Event
from model.frontier import Frontier
from model.vector_clock import VectorClock as VC
from model.initial_event import create_initial_system_event
from typing import Set


def _create_fsm_from_source(spec_source: str, test_specific_processes: Set[str] = None) -> EPBlockFSM:
    """
    Parses a PBTL formula string, transforms it to DLNF,
    creates an EPBlockFSM instance, and performs minimal Monitor-like setup
    including seeding with a system-wide initial frontier.
    """
    dlnf_ast = parse_and_dlnf(spec_source)
    from parser.ast_nodes import Or, EP  # Local import for AST node types
    if isinstance(dlnf_ast, Or):
        ep_ast_node = dlnf_ast.left
        if not isinstance(ep_ast_node, EP):  # Should be EP for these tests
            raise ValueError(f"Expected EP node from Or.left, got {type(ep_ast_node)}")
    elif isinstance(dlnf_ast, EP):
        ep_ast_node = dlnf_ast
    else:  # Should not happen if parser and DLNF work
        raise ValueError(f"Expected EP or Or node from DLNF, got {type(dlnf_ast)}")

    fsm = EPBlockFSM.from_ep(ep_ast_node)

    # Determine system processes for this unit test FSM instance.
    # _create_simple_frontier defaults to process "P".
    system_procs_for_this_test_fsm = {"P"}  # Default process used in most simple frontiers for tests
    if test_specific_processes:
        system_procs_for_this_test_fsm.update(test_specific_processes)

    # Create the initial system event and frontier based on these processes.
    # This mimics what the Monitor would do with a '# system_processes' directive.
    initial_event = create_initial_system_event(system_procs_for_this_test_fsm)
    initial_frontier = Frontier(
        {proc: initial_event for proc in initial_event.processes}
    )
    # If initial_event.processes was empty (due to placeholder logic in create_initial_system_event
    # if system_procs_for_this_test_fsm was empty), create a minimal valid frontier.
    if not initial_event.processes:
        initial_frontier = Frontier({"_placeholder_test_init": initial_event})

    # Set infrastructure (including known processes) and then seed with the initial frontier.
    fsm.set_infrastructure(known_processes=system_procs_for_this_test_fsm.copy(),
                           successor_lookup=None)  # Successor lookup not used by fsm.update driven tests
    fsm.seed_with_iota_update(initial_frontier)  # Pass the correctly formed initial system frontier

    return fsm


def _create_simple_frontier(props: set[str], time_step: int = 1, process_id: str = "P") -> Frontier:
    """Creates a simple single-process frontier for testing."""
    event_id = f"e{time_step}_{'_'.join(sorted(list(props)))}" if props else f"e{time_step}_empty"
    event = Event(
        eid=event_id,
        processes=frozenset({process_id}),
        vc=VC({process_id: time_step}),
        props=frozenset(props)
    )
    return Frontier({process_id: event})


def _drive_fsm_with_frontiers(fsm: EPBlockFSM, prop_sets_sequence: list[set[str]], process_id: str = "P"):
    """Updates the FSM with a sequence of simple single-process frontiers."""
    for i, props in enumerate(prop_sets_sequence, 1):
        frontier = _create_simple_frontier(props, time_step=i, process_id=process_id)
        fsm.update(frontier)


class TestEPBlockFSMLogic:
    """
    Unit tests for EPBlockFSM, focusing on its response to frontiers via update()
    and the logic from Table 1 of the reference paper.
    """

    # --- Row 1: P-blocks only ---
    def test_row1_p_only_all_p_blocks_satisfied_succeeds(self):
        fsm = _create_fsm_from_source("EP(EP(p) & EP(q))")
        _drive_fsm_with_frontiers(fsm, [{'p'}, {'q'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row1_p_only_not_all_p_blocks_satisfied_final_false(self):
        fsm = _create_fsm_from_source("EP(EP(p) & EP(q))")
        _drive_fsm_with_frontiers(fsm, [set(), set()])
        assert fsm.verdict() is Verdict.INCONCLUSIVE
        fsm.finalize_at_trace_end()
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 2: P-blocks and M-literals ---
    def test_row2_p_and_m_all_satisfied_succeeds(self):
        fsm = _create_fsm_from_source("EP(EP(p) & a & b)")
        _drive_fsm_with_frontiers(fsm, [{'p'}, {'a', 'b'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row2_p_and_m_m_literals_not_fully_satisfied_final_false(self):
        fsm = _create_fsm_from_source("EP(EP(p) & a & b)")
        _drive_fsm_with_frontiers(fsm, [{'p'}, {'a'}])
        assert fsm.verdict() is Verdict.INCONCLUSIVE
        fsm.finalize_at_trace_end()
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 3: P-blocks and N-blocks ---
    def test_row3_p_and_n_p_satisfied_n_not_violated_succeeds(self):
        fsm = _create_fsm_from_source("EP(EP(p) & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'p'}, set(), set()])
        assert fsm.verdict() is Verdict.TRUE

    def test_row3_p_and_n_n_block_violated_fails(self):
        fsm = _create_fsm_from_source("EP(EP(p) & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'r'}])
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 4: P-blocks, M-literals, and N-blocks ---
    def test_row4_p_m_n_all_conditions_met_succeeds(self):
        fsm = _create_fsm_from_source("EP(EP(p) & x & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'p'}, {'x'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row4_p_m_n_n_block_violated_before_m_satisfied_fails(self):
        fsm = _create_fsm_from_source("EP(EP(p) & x & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'r'}])
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 5: M-literals only ---
    def test_row5_m_only_all_m_literals_satisfied_succeeds(self):
        fsm = _create_fsm_from_source("EP(a & b)")
        _drive_fsm_with_frontiers(fsm, [{'a', 'b'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row5_m_only_m_literals_not_fully_satisfied_final_false(self):
        fsm = _create_fsm_from_source("EP(a & b)")
        _drive_fsm_with_frontiers(fsm, [{'a'}, set()])
        assert fsm.verdict() is Verdict.INCONCLUSIVE
        fsm.finalize_at_trace_end()
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 6: N-blocks only ---
    def test_row6_n_only_no_n_block_violation_on_init_succeeds_terminally(self):
        fsm = _create_fsm_from_source("EP(!EP(r))")
        assert fsm.verdict() is Verdict.TRUE
        _drive_fsm_with_frontiers(fsm, [set(), set()])
        assert fsm.verdict() is Verdict.TRUE

    def test_row6_n_only_n_block_violation_after_init_success_remains_true(self):
        fsm = _create_fsm_from_source("EP(!EP(r))")
        assert fsm.verdict() is Verdict.TRUE
        _drive_fsm_with_frontiers(fsm, [{'r'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row6_n_only_iota_n_block_violation_on_init_fails_terminally(self):
        fsm = _create_fsm_from_source("EP(!EP(iota))")
        assert fsm.verdict() is Verdict.FALSE
        _drive_fsm_with_frontiers(fsm, [{'r'}])
        assert fsm.verdict() is Verdict.FALSE

    # --- Row 7: M-literals and N-blocks ---
    def test_row7_m_and_n_m_satisfied_n_not_violated_succeeds(self):
        fsm = _create_fsm_from_source("EP(x & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'x'}])
        assert fsm.verdict() is Verdict.TRUE

    def test_row7_m_and_n_n_block_violated_before_m_satisfied_fails(self):
        fsm = _create_fsm_from_source("EP(x & !EP(r))")
        _drive_fsm_with_frontiers(fsm, [{'r'}])
        assert fsm.verdict() is Verdict.FALSE