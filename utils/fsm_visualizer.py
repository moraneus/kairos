# logic/fsm_visualizer.py

import os
from typing import TYPE_CHECKING, Optional
from utils.logger import get_logger
from logic.verdict import Verdict

# Conditional import of graphviz
try:
    from graphviz import Digraph

    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False

# Type hint for EPBlockFSM to avoid circular imports
if TYPE_CHECKING:
    from logic.ep_block_fsm import EPBlockFSM
    from model.frontier import Frontier

logger = get_logger(__name__)

VISUALIZATION_OUTPUT_FOLDER = "fsm_visualizations"


def _format_frontier_for_display(fr: Optional['Frontier']) -> str:
    """
    Helper function to create a descriptive string for a Frontier object
    for display in visualizations. Includes its event composition and vector clock.
    """
    if fr is None:
        return "N/A"

    frontier_str = str(fr)

    vc_str = "VC:N/A"
    if hasattr(fr, 'vc') and fr.vc is not None:
        vc_str = f"VC:{str(fr.vc)}"

    return f"{frontier_str} {vc_str}"


def visualize_ep_block_fsm_state(fsm: 'EPBlockFSM', base_filename: str, fmt: str = "png") -> None:
    """
    Generates a visualization of an EPBlockFSM's current state using Graphviz.
    The output image is saved to a dedicated folder ('fsm_visualizations').
    Frontier IDs in labels are now more descriptive, showing event composition and VC.

    Args:
        fsm: The EPBlockFSM instance to visualize.
        base_filename: The base name for the output file.
        fmt: The output format for the image (e.g., "png", "svg").
    """
    if not GRAPHVIZ_AVAILABLE:
        logger.warning("Graphviz library not installed. Skipping FSM state visualization. "
                       "To enable, install graphviz: pip install graphviz")
        return

    dot = Digraph(comment=f"FSM State for {fsm.ep}", format=fmt)
    dot.attr(rankdir="TB", newrank="true", splines="ortho", nodesep="0.6", ranksep="0.5")

    # Ensure the output directory exists and define output_path
    if not os.path.exists(VISUALIZATION_OUTPUT_FOLDER):
        try:
            os.makedirs(VISUALIZATION_OUTPUT_FOLDER)
            logger.info(f"Created directory for FSM visualizations: {VISUALIZATION_OUTPUT_FOLDER}")
            output_path = os.path.join(VISUALIZATION_OUTPUT_FOLDER, base_filename)
        except OSError as e:
            logger.error(f"Could not create directory {VISUALIZATION_OUTPUT_FOLDER}: {e}. "
                         f"Saving to current directory instead.")
            output_path = base_filename  # Fallback
    else:
        output_path = os.path.join(VISUALIZATION_OUTPUT_FOLDER, base_filename)

    state = fsm.state

    # --- Central Verdict Node ---
    verdict_val = fsm.verdict().name
    verdict_color = {"TRUE": "palegreen", "FALSE": "lightcoral", "INCONCLUSIVE": "lightgrey"}.get(verdict_val, "white")
    dot.node("VERDICT", f"FSM Verdict:\n{verdict_val}", shape="box", style="filled", fillcolor=verdict_color,
             fontsize="12")

    # --- P-Blocks Cluster ---
    if state.p:
        with dot.subgraph(name="cluster_P_Blocks") as p_cluster:
            p_cluster.attr(label="P-Blocks (EP(...))", style="filled", color="lightskyblue", fontsize="10")
            all_p_satisfied_fr = state.first_all_p_conjunctive_satisfaction_frontier
            p_conj_node_id = "P_CONJUNCTION"
            p_conj_label = "All P-Blocks Met?"
            p_conj_color = "lightgrey"

            if all_p_satisfied_fr:
                p_conj_label += f"\n(Yes, at Frontier: {_format_frontier_for_display(all_p_satisfied_fr)})"
                p_conj_color = "palegreen"
            else:
                p_conj_label += "\n(No)"
                p_conj_color = "lightcoral" if (fsm.verdict() == Verdict.FALSE and state.failure and
                                                any(not p_bs.satisfied_at for p_bs in state.p)) else "lightgrey"

            p_cluster.node(p_conj_node_id, p_conj_label, shape="box", style="filled", fillcolor=p_conj_color)
            dot.edge(p_conj_node_id, "VERDICT", style="dotted", arrowhead="none", constraint="false")

            for i, p_block_state in enumerate(state.p):
                node_id = f"P_{i}"
                label = f"P{i}: {str(p_block_state.formula)}"
                color = "lightgrey"
                if p_block_state.satisfied_at:
                    label += f"\n(Met at: {_format_frontier_for_display(p_block_state.satisfied_at)})"
                    color = "palegreen"
                elif fsm.verdict() == Verdict.FALSE and state.failure:
                    color = "lightcoral"
                p_cluster.node(node_id, label, style="filled", fillcolor=color)
                p_cluster.edge(node_id, p_conj_node_id, style="dashed", arrowhead="none")

    # --- M-Literals Cluster ---
    if state.m:
        with dot.subgraph(name="cluster_M_Literals") as m_cluster:
            m_cluster.attr(label="M-Literals (Current State)", style="filled", color="lightgoldenrodyellow",
                           fontsize="10")
            m_overall_node_id = "M_CONJUNCTION"
            m_satisfied_fr = state.m_satisfaction_frontier
            m_label = "All M-Literals Met?"
            m_color = "lightgrey"

            if m_satisfied_fr:
                m_label += f"\n(Yes, at Frontier: {_format_frontier_for_display(m_satisfied_fr)})"
                m_color = "palegreen"
            else:
                m_label += "\n(No)"
                if fsm.verdict() == Verdict.FALSE and state.failure:
                    m_color = "lightcoral"

            m_cluster.node(m_overall_node_id, m_label, shape="box", style="filled", fillcolor=m_color)
            if state.p:
                dot.edge("P_CONJUNCTION", m_overall_node_id, label="then", dir="forward", constraint="true")
            else:
                dot.edge(m_overall_node_id, "VERDICT", style="dotted", arrowhead="none", constraint="false")

            for i, m_block_state in enumerate(state.m):
                node_id = f"M_{i}"
                label = f"M{i}: {str(m_block_state.formula)}"
                m_cluster.node(node_id, label, style="filled", fillcolor="lightgrey")
                m_cluster.edge(node_id, m_overall_node_id, style="dashed", arrowhead="none")

    # --- N-Blocks Cluster ---
    if state.n:
        with dot.subgraph(name="cluster_N_Blocks") as n_cluster:
            n_cluster.attr(label="N-Blocks (!EP(...))", style="filled", color="lightpink", fontsize="10")
            n_conj_node_id = "N_CONJUNCTION_CHECK"
            n_conj_label = "All N-Blocks Valid\n(!EP(...) holds for all)?"
            n_conj_color = "palegreen"

            trigger_frontier_for_n_check = None
            if state.m_satisfaction_frontier:
                trigger_frontier_for_n_check = state.m_satisfaction_frontier
            elif state.p and state.first_all_p_conjunctive_satisfaction_frontier and not state.m:
                trigger_frontier_for_n_check = state.first_all_p_conjunctive_satisfaction_frontier

            if trigger_frontier_for_n_check:
                for n_block_state in state.n:
                    if n_block_state.satisfied_at and not (trigger_frontier_for_n_check < n_block_state.satisfied_at):
                        n_conj_label = "N-Block Violation Prevented Success"
                        n_conj_color = "lightcoral"
                        break
            elif any(n_bs.satisfied_at for n_bs in state.n) and fsm.verdict() == Verdict.FALSE:
                n_conj_label = "N-Block Violation Contributed to Failure"
                n_conj_color = "lightcoral"
            elif not any(n_bs.satisfied_at for n_bs in
                         state.n) and fsm.verdict() == Verdict.TRUE and not state.m and not state.p:
                n_conj_label = "N-Blocks Valid (Succeeded)"
                n_conj_color = "palegreen"

            n_cluster.node(n_conj_node_id, n_conj_label, shape="box", style="filled", fillcolor=n_conj_color)
            if state.m:
                dot.edge("M_CONJUNCTION", n_conj_node_id, label="and", dir="forward", constraint="true")
            elif state.p:
                dot.edge("P_CONJUNCTION", n_conj_node_id, label="and", dir="forward", constraint="true")
            dot.edge(n_conj_node_id, "VERDICT", style="dotted", arrowhead="none", constraint="false")

            for i, n_block_state in enumerate(state.n):
                node_id = f"N_{i}"
                label = f"N{i}: !{str(n_block_state.formula)}"
                sub_label = "\n(EP(...) is False - N-block VALID)"
                color = "palegreen"

                if n_block_state.satisfied_at:
                    sub_label = f"\n(EP(...) True at: {_format_frontier_for_display(n_block_state.satisfied_at)}) - N-block VIOLATED"
                    color = "lightcoral"
                label += sub_label
                n_cluster.node(node_id, label, style="filled", fillcolor=color)
                n_cluster.edge(node_id, n_conj_node_id, style="dashed", arrowhead="none")

    # Final direct edges for simple cases
    if state.p and not state.m and not state.n:
        dot.edge("P_CONJUNCTION", "VERDICT", style="solid", arrowhead="normal", constraint="false")
    elif not state.p and state.m and not state.n:
        dot.edge("M_CONJUNCTION", "VERDICT", style="solid", arrowhead="normal", constraint="false")
    elif not state.p and not state.m and state.n:
        dot.edge("N_CONJUNCTION_CHECK", "VERDICT", style="solid", arrowhead="normal", constraint="false")

    try:
        dot.render(output_path, view=False, cleanup=True)  # output_path is now always defined before this line
        logger.info(f"FSM state visualization saved to {output_path}.{fmt}")
    except Exception as e:
        # Check if output_path was defined (it should be, but for robustness in error message)
        path_for_error_msg = output_path if 'output_path' in locals() else base_filename
        logger.warning(f"Failed to render FSM state visualization to {path_for_error_msg}.{fmt}: {e}. "
                       "Ensure Graphviz executables (dot) are in your system's PATH.")