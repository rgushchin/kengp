# Kengp: Linux Kernel Engineering AI Toolkit

This repository contains a specialized environment and toolkit for AI-assisted Linux kernel development and review. While currently oriented toward Gemini, it is designed to be compatible with other AI tools and models, such as Claude. The toolkit helps developers and maintainers adhere to strict upstream Linux kernel standards by automating parts of the review and verification workflow.

## Features

*   **AI-Assisted Review:** Includes `ai_review.py` to automate code reviews using specialized prompts, primarily optimized for Gemini but adaptable for other models.
*   **Subsystem-Specific Prompts:** A collection of review prompts in `review-prompts/` tailored for various kernel subsystems (block, mm, net, sched, etc.).
*   **Semantic Code Analysis:** Integrates with `semcode` (built via `setup.sh`) for semantic code search and understanding.
*   **Maintainer Persona:** `AGENT.md` defines the persona and standards for the AI agent, ensuring code and commit messages meet the high bar of the Linux kernel community.
*   **Linux Kernel Source:** Includes the Linux kernel source tree in `linux/`.

## Prerequisites

*   Linux environment
*   Rust toolchain (for building `semcode`)
*   Python 3

## Setup

Run the setup script to initialize submodules and build the necessary tools:

```bash
./setup.sh
```

## Directory Structure

*   `linux/`: The Linux kernel source tree.
*   `semcode/`: Source code for the semantic analysis tool.
*   `review-prompts/`: Markdown files containing system prompts for AI-driven reviews.
*   `ai_review.py`: Script to drive the review process (Gemini-oriented by default).
*   `AGENT.md`: The core system prompt defining the developer persona and guidelines.
*   `eng.md`: Detailed guidance on how to create and validate kernel changes.
