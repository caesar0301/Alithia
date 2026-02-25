#!/bin/bash
# Run PaperScout agent with configuration from file or environment variables
#
# Usage:
#   ./scripts/run_paperscout.sh [OPTIONS]
#   ./scripts/run_paperscout.sh --help
#
# Configuration:
#   --config FILE: Use specific configuration file (optional)
#   Without --config: Agent uses environment variables for configuration

set -e

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run PaperScout agent to fetch and analyze ArXiv papers.

Options:
    -h, --help          Show this help message and exit
    --from-date DATE    Start date for paper search (format: YYYY-MM-DD)
    --to-date DATE      End date for paper search (format: YYYY-MM-DD)
    --config FILE       Path to configuration file (optional)
    --fill-gaps         Run Gap Scanner to fill missing notification dates

Configuration:
    If --config is provided, the agent uses the specified configuration file.
    Otherwise, the agent loads configuration from environment variables.
    See agent documentation for supported environment variables.

Examples:
    # Run with environment variables (no config file)
    ./scripts/run_paperscout.sh

    # Run with specific date range
    ./scripts/run_paperscout.sh --from-date 2024-01-01 --to-date 2024-01-07

    # Run with custom config file
    ./scripts/run_paperscout.sh --config my_config.json

    # Run with config file and date range
    ./scripts/run_paperscout.sh --config my_config.json --from-date 2024-01-01

    # Fill gaps (retry missed dates)
    ./scripts/run_paperscout.sh --config my_config.json --fill-gaps

EOF
    exit 0
}

ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        --from-date)
            ARGS+=("--from-date" "$2")
            shift 2
            ;;
        --to-date)
            ARGS+=("--to-date" "$2")
            shift 2
            ;;
        --config)
            ARGS+=("--config" "$2")
            shift 2
            ;;
        --fill-gaps)
            ARGS+=("--fill-gaps")
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "Running PaperScout agent..."
python -m alithia.run paperscout_agent "${ARGS[@]}"
echo "PaperScout agent completed successfully"
