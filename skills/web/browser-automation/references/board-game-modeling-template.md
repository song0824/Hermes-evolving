# Board Game Rule Extraction → Mathematical Model Template

When extracting rules from a tutorial video and building a mathematical model, use this structure.

## Output Structure

### 1. Game Overview Table
| Dimension | Value |
|-----------|-------|
| Type | Area control / card-driven / resource management / etc. |
| Players | N (symmetric / asymmetric) |
| Factions | List of factions/players |
| Core mechanics | List key mechanics |

### 2. Core Mathematical Models

For each mechanic, provide:
- **Formula** in LaTeX notation
- **Variable definitions** in a table
- **Concrete examples** from the video

Common model types for board games:
- **Control/Conflict**: argmax over strength functions
- **Resource economics**: vector constraints and transformations
- **Scoring**: additive VP formulas with penalty terms
- **State space**: matrix/tensor representation of game state
- **Turn structure**: phased action sequences

### 3. State Space Representation
Define the complete game state as a tuple of matrices/vectors.

### 4. Strategy Analysis
- Value functions for decisions
- Priority scoring formulas
- Trade-off parameters

### 5. Known Mechanisms Table
Summarize each observed mechanic with its mathematical expression.

### 6. Pending Information
List rules/mechanics not yet confirmed from the video.

## Tips
- Use `browser_vision` at 5-10 timestamps for a 10-minute tutorial
- Focus on: player boards, cards with text, score tracks, resource tokens, subtitle text
- Subtitle text is often the clearest source of rule names and descriptions
- Yellow/red annotation overlays in videos highlight the current rule being explained
- Build the model incrementally — each timestamp adds pieces
