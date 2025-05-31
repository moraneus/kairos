# Kairos - A PBTL Runtime Verification Tool

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

> *"Καιρός (Kairos) - the right time, the opportune moment"*

Kairos is a sophisticated runtime verification tool for distributed systems that monitors Past-Based Temporal Logic (PBTL) properties over partial order executions. Named after the ancient Greek concept of *kairos* - representing the opportune or decisive moment in time - this tool captures the essence of temporal reasoning in distributed systems where timing and causality are crucial for correctness.

## Table of Contents

- [About Kairos](#about-kairos)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [PBTL Logic Specification](#pbtl-logic-specification)
- [Trace File Format](#trace-file-format)
- [Docker Usage](#docker-usage)
- [Documentation](#documentation)
- [Examples](#examples)
- [Architecture](#architecture)
- [Limitations and Known Issues](#limitations-and-known-issues)
- [Contributing](#contributing)
- [License](#license)
- [Academic References](#academic-references)

## About Kairos

### The Philosophy of Time

In ancient Greek philosophy, there were two concepts of time:

- **Chronos (Χρόνος)**: Quantitative time - the sequential, measurable ticking of moments
- **Kairos (Καιρός)**: Qualitative time - the right, critical, or opportune moment when something significant happens

Traditional runtime verification tools operate in *chronos* - they monitor systems through linear sequences of events in chronological order. However, distributed systems exist in *kairos* - where the significance lies not just in when events occur, but in their causal relationships and the opportune moments when system properties can be meaningfully evaluated.

### Why Kairos?

Kairos embodies this philosophy by:

1. **Capturing Causality**: Understanding that in distributed systems, "when" is less important than "in what causal order"
2. **Recognizing Opportune Moments**: Identifying the right global states where temporal properties can be meaningfully evaluated
3. **Respecting Partial Order**: Acknowledging that concurrent events in distributed systems don't have a universal ordering
4. **Enabling Temporal Reasoning**: Providing tools to reason about the past states of distributed computations

## Features

### Core Capabilities

- **PBTL Monitoring**: Full support for Past-Based Temporal Logic with EP (Exists in Past) operators
- **Partial Order Semantics**: Native support for partial order executions and causal relationships
- **Vector Clock Integration**: Automatic causal ordering using Lamport's vector clock algorithm
- **Distributed Event Processing**: Handles out-of-order event delivery with causal consistency
- **Real-time Monitoring**: Online monitoring with incremental verdict computation

### Advanced Features

- **Formula Parsing**: Complete PBTL grammar with boolean operators and temporal constructs
- **DLNF Transformation**: Automatic conversion to Disjunctive Literal Normal Form for efficient monitoring
- **Multi-process Support**: Handles complex distributed systems with multiple concurrent processes
- **Frontier Management**: Sophisticated global state tracking using consistent cuts
- **Comprehensive Testing**: Extensive test suite with real-world examples and edge cases

### Algorithmic Foundation

Kairos implements the state-of-the-art PBTL runtime verification algorithm, featuring:

- **Complete Case Analysis**: Implementation of all monitoring cases (P-only, P+M, P+M+N, etc.)
- **Causal Constraint Checking**: Sophisticated N-block constraint validation using vector clocks
- **Optimal Complexity**: Linear complexity in events and processes for the PBTL subset
- **Early Termination**: Smart detection of conclusive verdicts for improved performance

## Installation

### System Requirements

- **Python**: 3.8 or higher (recommended: 3.11+)
- **Memory**: Minimum 512MB RAM (depends on trace size and formula complexity)
- **Storage**: Minimal storage requirements for traces and results

### Dependencies

Kairos requires the following Python packages:

```bash
# Core dependencies (requirements.txt)
sly>=0.5                    # Parser generator for PBTL grammar
dataclasses-json>=0.6       # JSON serialization support

# Development dependencies (requirements-dev.txt)  
pytest>=7.0                 # Testing framework
pytest-cov>=4.0            # Coverage reporting
black>=22.0                 # Code formatting
mypy>=1.0                  # Type checking
isort>=5.0                 # Import sorting
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/kairos.git
cd kairos
```

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

```bash
# Install dependencies
pip install -r requirements.txt
```

```bash
# Run tests to verify installation
python -m pytest tests/ -v
```

### Development Installation

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/kairos.git
cd kairos
```

```bash
# Set up development environment
python -m venv venv
source venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
```

```bash
# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=core --cov=parser --cov=utils --cov-report=html
```

### Code Style

We use:
- **Black** for code formatting
- **isort** for import sorting  
- **mypy** for type checking
- **pytest** for testing

```bash
# Format code
black .
isort .

# Type checking
mypy core/ parser/ utils/

# Run all checks
pre-commit run --all-files
```

## Quick Start

### Basic Usage

1. **Create a PBTL property file** (`property.pbtl`): `EP(EP(ready) & EP(confirmed) & !EP(error))`
2. **Create a trace file** (`trace.csv`):
    ```csv
    # system_processes: P1|P2|P3
    eid,processes,vc,props
    init,P1,P1:1;P2:0;P3:0,iota
    ready_event,P1,P1:2;P2:0;P3:0,ready
    confirm_event,P2,P1:0;P2:1;P3:0,confirmed
    final_event,P3,P1:0;P2:0;P3:1,done
    ```
3. **Run the monitor:**
    ```bash
    python run_monitor.py -p property.pbtl -t trace.csv -v 
    ```

### Command Line Options
```bash
python run_monitor.py --help

Options:
  -p, --property PATH     Path to PBTL property file [required]
  -t, --trace PATH        Path to CSV trace file [required]
  -v, --verbose           Enable verbose output
  --debug                 Enable debug output
  --validate-only         Only validate trace file format
  --stop-on-verdict       Stop processing when verdict becomes conclusive
  --debug-final           Print detailed final state analysis
```

### Example Output
```bash
📋 Property loaded: EP(EP(a) & EP(b) & EP(c) & !EP(d))
✅ Formula syntax is well-formed
🔍 Validating trace file: playground/trace2.csv
Initialized with processes: ['PA', 'PB', 'PC', 'PD', 'PV']
=== Starting Evaluation ===
Property: EP(EP(a) & EP(b) & EP(c) & !EP(d))
Initial verdict: FALSE (Inconclusive)
Initial System Frontier: ⟨PA:iota, PB:iota, PC:iota, PD:iota, PV:iota⟩
pa_int1@PA:[PA:1, PB:0, PC:0, PD:0, PV:0] → frontiers=['⟨PA:pa_int1, PB:iota, PC:iota, PD:iota, PV:iota⟩'], verdict=FALSE (Inconclusive)
pb_int2@PB:[PA:0, PB:1, PC:0, PD:0, PV:0] → frontiers=['⟨PA:pa_int1, PB:pb_int2, PC:iota, PD:iota, PV:iota⟩'], verdict=FALSE (Inconclusive)
pc_int3@PC:[PA:0, PB:0, PC:1, PD:0, PV:0] → frontiers=['⟨PA:pa_int1, PB:pb_int2, PC:pc_int3, PD:iota, PV:iota⟩'], verdict=FALSE (Inconclusive)
pd_int4@PD:[PA:0, PB:0, PC:0, PD:1, PV:0] → frontiers=['⟨PA:pa_int1, PB:pb_int2, PC:pc_int3, PD:pd_int4, PV:iota⟩'], verdict=FALSE (Inconclusive)
pa_pv_comm5@PA,PV:[PA:2, PB:0, PC:0, PD:0, PV:1] → frontiers=['⟨PA:pa_pv_comm5, PB:pb_int2, PC:pc_int3, PD:pd_int4, PV:pa_pv_comm5⟩'], verdict=FALSE (Inconclusive)
pd_pv_comm6@PD,PV:[PA:2, PB:0, PC:0, PD:2, PV:2] → frontiers=['⟨PA:pa_pv_comm5, PB:pb_int2, PC:pc_int3, PD:pd_pv_comm6, PV:pd_pv_comm6⟩'], verdict=FALSE (Inconclusive)
pv_decide7@PV:[PA:2, PB:0, PC:0, PD:2, PV:3] → frontiers=['⟨PA:pa_pv_comm5, PB:pb_int2, PC:pc_int3, PD:pd_pv_comm6, PV:pv_decide7⟩'], verdict=FALSE (Inconclusive)
pa_int8@PA:[PA:3, PB:0, PC:0, PD:0, PV:1] → frontiers=['⟨PA:pa_int8, PB:pb_int2, PC:pc_int3, PD:pd_pv_comm6, PV:pv_decide7⟩'], verdict=FALSE (Inconclusive)
pb_int9@PB:[PA:0, PB:2, PC:0, PD:0, PV:0] → frontiers=['⟨PA:pa_int8, PB:pb_int9, PC:pc_int3, PD:pd_pv_comm6, PV:pv_decide7⟩'], verdict=FALSE (Inconclusive)
pc_int10@PC:[PA:0, PB:0, PC:2, PD:0, PV:0] → frontiers=['⟨PA:pa_int8, PB:pb_int9, PC:pc_int10, PD:pd_pv_comm6, PV:pv_decide7⟩'], verdict=FALSE (Inconclusive)
pd_int11@PD:[PA:2, PB:0, PC:0, PD:3, PV:2] → frontiers=['⟨PA:pa_int8, PB:pb_int9, PC:pc_int10, PD:pd_int11, PV:pv_decide7⟩'], verdict=FALSE (Inconclusive)
pa_pv_comm12@PA,PV:[PA:4, PB:0, PC:0, PD:2, PV:4] → frontiers=['⟨PA:pa_pv_comm12, PB:pb_int9, PC:pc_int10, PD:pd_int11, PV:pa_pv_comm12⟩'], verdict=FALSE (Inconclusive)
pc_pv_comm13@PC,PV:[PA:4, PB:0, PC:3, PD:2, PV:5] → frontiers=['⟨PA:pa_pv_comm12, PB:pb_int9, PC:pc_pv_comm13, PD:pd_int11, PV:pc_pv_comm13⟩'], verdict=FALSE (Inconclusive)
pv_decide14@PV:[PA:4, PB:0, PC:3, PD:2, PV:6] → frontiers=['⟨PA:pa_pv_comm12, PB:pb_int9, PC:pc_pv_comm13, PD:pd_int11, PV:pv_decide14⟩'], verdict=FALSE (Inconclusive)
pa_int15@PA:[PA:5, PB:0, PC:0, PD:2, PV:4] → frontiers=['⟨PA:pa_int15, PB:pb_int9, PC:pc_pv_comm13, PD:pd_int11, PV:pv_decide14⟩'], verdict=TRUE

>>> FINAL VERDICT: TRUE <<<
```

## PBTL Logic Specification
### Grammar
```text
<formula> ::= <atom>
           | <formula> & <formula>    // conjunction
           | <formula> | <formula>    // disjunction  
           | ! <formula>              // negation
           | EP(<formula>)            // exists in past
           | ( <formula> )            // grouping
           | TRUE | FALSE             // boolean constants

<atom> ::= <identifier>               // propositional variable
```

### Operators and Semantics
Kairos supports Past-Based Temporal Logic (PBTL) with the following operators:

#### Boolean Operators

- `TRUE`, `FALSE`: Boolean constants for truth and falsehood
- `p & q`: Conjunction - true when both p and q are true
- `p | q`: Disjunction - true when at least one of p or q is true
- `! p`: Negation - true when p is false

#### Temporal Operators

- `EP(φ)`: "Exists in Past" - true if formula φ was satisfied at some point in the past along at least one execution path

#### Operator Precedence (highest to lowest)
1. `()` - parentheses for grouping
2. `EP(...)` - temporal operator
3. `!` - negation (right-associative)
4. `&` - conjunction (left-associative)
5. `|` - disjunction (left-associative)

This follows standard mathematical and logical conventions where:

- Parentheses have the highest precedence (they override everything else).
- Function-like operators `(EP)` come next.
- Unary operators (negation) come before binary operators.
- Conjunction (AND) binds tighter than disjunction (OR).

This means that `!p & q | r` would be parsed as `((!p) & q) | r`, and `EP(p | q) & r` would be parsed as `(EP(p | q)) & r`.

#### Semantic Notes

- PBTL formulas are evaluated over global states (frontiers) rather than individual events.
- The past is determined by the causal ordering in distributed systems, not chronological time. 
- `EP(φ)` searches for satisfaction along any causally consistent execution path 
- Properties are evaluated incrementally as new events arrive

#### Example Formulas
```text
# Simple past existence  
EP(ready)                              # "ready" occurred at some point in the past

# Conjunction of past events
EP(EP(init) & EP(ready))               # Both "init" and "ready" occurred in the past

# Safety properties
EP(EP(success) & !EP(error))          # Success occurred but no error ever occurred

# Complex temporal relationships  
EP((EP(request) & EP(response)) | EP(timeout))  # Either request-response completed or timeout occurred
```

## Trace File Format
### CSV Structure
Trace files use CSV format with the following structure:
```csv
# Optional: system_processes directive
# system_processes: ProcessA|ProcessB|ProcessC

# Required headers
eid,processes,vc,props

# Event records
event_id,process_list,vector_clock,propositions
```

### Field Descriptions
* `eid`: Event identifier (string) - unique name for each event
* `processes`: Pipe-separated process IDs participating in the event 
  * Single process: `"P1"`
  * Multiple processes: `"P1|P2|P3"`.
* `vc`: Semicolon-separated vector clock entries in format `Process:Timestamp` 
  * Example: `"P1:2;P2:1;P3:0"`.
  * Must include all processes in the system. 
* `props`: Pipe-separated proposition names that hold after event execution 
  * `Example`: "ready|confirmed"
  * May be empty for events with no propositions

### Vector Clock Rules
* Each process maintains a logical timestamp. 
* Timestamps increment for events involving that process. 
* Vector clocks must respect causality (events can only be delivered when all prior events have been seen).

### Example Trace
```csv
# system_processes: Client|Server|Database
eid,processes,vc,props
client_start,Client,Client:1;Server:0;Database:0,init|ready
server_req,Client|Server,Client:2;Server:1;Database:0,request|sync
db_query,Server|Database,Client:2;Server:2;Database:1,query|db_access
db_response,Database,Client:2;Server:2;Database:2,response|data_ready
server_resp,Server,Client:2;Server:3;Database:2,response|completed
client_done,Client,Client:3;Server:3;Database:2,done|satisfied
```

## Docker Usage

Kairos provides a Docker container for easy deployment and isolated execution.

### Building the Docker Image

```bash
# Build the image
docker build -t kairos:latest .

# Or build with specific version
docker build -t kairos:1.0.0 .
```

### Running with Docker

#### Basic Monitoring

```bash
# Create a directory for your files
mkdir kairos-workspace
cd kairos-workspace

# Create your property and trace files
echo "EP(EP(ready) & !EP(error))" > property.pbtl

# Create trace file
cat > trace.csv << EOF
# system_processes: P1|P2
eid,processes,vc,props
ev1,P1,P1:1;P2:0,ready
ev2,P2,P1:1;P2:1,done
EOF

# Run monitoring
docker run --rm -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv -v
 ```

#### Interactive Development

```bash
# Run interactive container for development
docker run -it --rm -v $(pwd):/workspace kairos:latest bash

# Inside container, you can:
# - Edit files in /workspace
# - Run tests: python -m pytest tests/ -v
# - Start monitoring: python run_monitor.py --help
```

#### Advanced Docker Usage

```bash
# Run with specific memory limits
docker run --rm --memory=512m -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv

# Run tests in container
docker run --rm kairos:latest python -m pytest tests/ -v

# Run with debug output
docker run --rm -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv --debug

# Validate trace file only
docker run --rm -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv --validate-only
 ```

### Docker Environment Variables

You can customize the Docker execution using environment variables:

```bash
# Set log level
docker run --rm -e LOG_LEVEL=DEBUG -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv

# Set Python path for custom modules
docker run --rm -e PYTHONPATH=/workspace/custom -v $(pwd):/workspace kairos:latest \
 python run_monitor.py -p /workspace/property.pbtl -t /workspace/trace.csv
 ```

## Documentation

### PBTL Formula Syntax

Kairos supports the following PBTL operators:
- `EP(φ)`           - "φ held at some point in the past"
- `φ & ψ`           - Conjunction
- `φ | ψ`           - Disjunction
- `!φ`              - Negation
- `true, false`     - Boolean constants
- `p, q, ready`     - Propositional variables

#### Example Formulas

```bash
# Simple past existence
EP(ready)

# Conjunction of past events
EP(EP(init) & EP(ready) & EP(confirmed))

# Avoiding bad states
EP(EP(success) & !EP(error))

# Complex disjunctive properties
EP((EP(path1) & EP(result1)) | (EP(path2) & EP(result2)))

# Temporal ordering constraints
EP(EP(request) & EP(response) & !EP(timeout))
```

## Examples

### Example 1: Simple Request-Response

**Property**: `EP(EP(request) & EP(response))`

```csv
eid,processes,vc,props
req,Client|Server,Client:1;Server:1,request
resp,Server|Client,Client:2;Server:2,response
```

**Result**: TRUE ✅

### Example 2: Error Detection

**Property**: `EP(EP(process_started) & !EP(fatal_error))`

```csv
eid,processes,vc,props
start,Worker,Worker:2,process_started
error,Worker,Worker:1,fatal_error
```

**Result**: FALSE ❌ (fatal_error violates the constraint)

### Example 3: Distributed Consensus

**Property**: `EP(EP(prepare) & EP(commit) & !EP(abort))`

```csv
eid,processes,vc,props
prep1,Node1,Node1:1;Node2:0;Node3:0,prepare
prep2,Node2,Node1:1;Node2:1;Node3:0,prepare  
prep3,Node3,Node1:1;Node2:1;Node3:1,prepare
commit,Node1|Node2|Node3,Node1:2;Node2:2;Node3:2,commit
```

**Result**: TRUE ✅

## Architecture

### Core Components

```text
kairos/
├── core/                   # Core monitoring engine
│   ├── monitor.py         # Main PBTL monitor implementation
│   ├── event.py           # Event and VectorClock classes
│   ├── frontier.py        # Global state representation
│   └── verdict.py         # Three-valued logic verdicts
├── parser/                # Formula parsing and transformation
│   ├── grammar.py         # PBTL grammar (SLY-based)
│   ├── lexer.py           # Lexical analyzer
│   ├── ast_nodes.py       # Abstract syntax tree nodes
│   └── dlnf_transformer.py # DLNF transformation
├── utils/                 # Utilities and helpers
│   ├── trace_reader.py    # CSV trace file parsing
│   └── logger.py          # Structured logging
└── tests/                 # Comprehensive test suite
    ├── core_tests/        # Unit tests for core components
    ├── parser_tests/      # Unit tests for parser components
    └── integration_tests/ # End-to-end integration tests
```

### Algorithm Implementation

Kairos implements the advanced PBTL monitoring algorithm with:

1. **Formula Parsing**: PBTL formulas → AST → DLNF
2. **Event Processing**: Causal delivery using vector clocks
3. **Frontier Management**: Global state evolution tracking
4. **Disjunct Evaluation**: Complete case analysis for different formula patterns
5. **Verdict Computation**: Three-valued logic with early termination

## Limitations and Known Issues

- **Memory Usage**: Formula complexity can lead to exponential memory usage in worst-case scenarios
- **Single Process**: Current implementation uses centralized monitoring (not distributed)
- **Formula Size**: DLNF transformation may cause exponential formula expansion
- **Vector Clock Overhead**: Large distributed systems may experience vector clock overhead

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

## Academic References

Kairos in academic work (relevant papers on PBTL monitoring):

```bibtex
TBD
```

## Acknowledgments

- Built upon research in distributed systems runtime verification
- Implements algorithms from the PBTL monitoring literature

---

*"In the realm of distributed systems, timing is not about the clock on the wall, but about the causal relationships that define the opportune moments for meaningful observation."*