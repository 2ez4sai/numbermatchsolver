import streamlit as st
import openpyxl
from io import BytesIO
from typing import NamedTuple, List, Tuple, Optional
import time

# ==========================================
# 1. CONFIGURATION & CORE DATA STRUCTURES
# ==========================================
EMPTY_CELL = 0
TARGET_SUM = 10
BOARD_WIDTH = 9


class Position(NamedTuple):
    row: int
    col: int

    def to_flat_index(self, width: int) -> int:
        return self.row * width + self.col

    @classmethod
    def from_flat_index(cls, index: int, width: int) -> 'Position':
        return cls(row=index // width, col=index % width)


class Move(NamedTuple):
    pos1: Position
    pos2: Position
    value1: int
    value2: int


class Board:
    def __init__(self, grid: List[List[int]]):
        # Filter out empty rows immediately on load if any exist
        self.grid = [list(row) for row in grid if any(cell != EMPTY_CELL for cell in row)]
        if not self.grid:
            self.grid = [[EMPTY_CELL] * BOARD_WIDTH]
        self.height = len(self.grid)
        self.width = BOARD_WIDTH

    def get_remaining_numbers_count(self) -> int:
        return sum(1 for row in self.grid for cell in row if cell != EMPTY_CELL)

    def to_tuple(self) -> Tuple[Tuple[int, ...], ...]:
        return tuple(tuple(row) for row in self.grid)

    def apply_move(self, move: Move) -> 'Board':
        """Applies a move and triggers row-collapse if a row becomes empty."""
        # Create deep copy of current grid
        new_grid = [list(row) for row in self.grid]

        # Clear selected positions
        new_grid[move.pos1.row][move.pos1.col] = EMPTY_CELL
        new_grid[move.pos2.row][move.pos2.col] = EMPTY_CELL

        # DYNAMIC RULE: Filter out rows that are entirely empty (Row-collapse / Shift Up)
        collapsed_grid = [row for row in new_grid if any(cell != EMPTY_CELL for cell in row)]

        return Board(collapsed_grid)


# ==========================================
# 2. PATHFINDER ENGINE (WITH SHIFT RULES)
# ==========================================
class Pathfinder:
    @staticmethod
    def get_legal_moves(board: Board) -> List[Move]:
        moves = []
        grid = board.grid
        height = board.height
        width = board.width

        # Flatten positions for easy wrapping & linear empty space scanning
        flat_positions: List[Position] = []
        for r in range(height):
            for c in range(width):
                flat_positions.append(Position(r, c))

        # 1. Horizontal Linear / Row Wrap Checking
        last_pos: Optional[Position] = None
        for pos in flat_positions:
            val = grid[pos.row][pos.col]
            if val != EMPTY_CELL:
                if last_pos is not None:
                    last_val = grid[last_pos.row][last_pos.col]
                    if Pathfinder._is_valid_pair(last_val, val):
                        moves.append(Move(last_pos, pos, last_val, val))
                last_pos = pos

        # 2. Geometric 2D Raycasting (Vertical and Diagonals)
        directions = [(1, 0), (1, 1), (1, -1)]  # Down, Diagonal-Right, Diagonal-Left

        for r in range(height):
            for c in range(width):
                val1 = grid[r][c]
                if val1 == EMPTY_CELL:
                    continue

                p1 = Position(r, c)
                for dr, dc in directions:
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < height and 0 <= nc < width:
                        val2 = grid[nr][nc]
                        if val2 != EMPTY_CELL:
                            if Pathfinder._is_valid_pair(val1, val2):
                                moves.append(Move(p1, Position(nr, nc), val1, val2))
                            break  # Path blocked by another active number
                        nr += dr
                        nc += dc
        return moves

    @staticmethod
    def _is_valid_pair(v1: int, v2: int) -> bool:
        return v1 == v2 or (v1 + v2) == TARGET_SUM


# ==========================================
# 3. SOLVER CORE (BRANCH & BOUND)
# ==========================================
class SolutionScore:
    def __init__(self, remaining_count: int, move_count: int):
        self.remaining_count = remaining_count
        self.move_count = move_count

    def is_better_than(self, other: 'SolutionScore') -> bool:
        if self.remaining_count != other.remaining_count:
            return self.remaining_count < other.remaining_count
        return self.move_count < other.move_count


class NumberMatchSolver:
    def __init__(self, initial_board: Board, max_seconds: float = 5.0):
        self.initial_board = initial_board
        self.transposition_table = {}
        self.best_sequence: List[Move] = []
        self.best_score = SolutionScore(initial_board.get_remaining_numbers_count(), float('inf'))
        self.max_seconds = max_seconds
        self.start_time = 0.0

    def solve(self) -> List[Move]:
        self.start_time = time.time()
        self._search(self.initial_board, [])
        return self.best_sequence

    def _search(self, current_board: Board, path: List[Move]) -> None:
        if time.time() - self.start_time > self.max_seconds:
            return

        board_state = current_board.to_tuple()
        remaining = current_board.get_remaining_numbers_count()
        current_score = SolutionScore(remaining_count=remaining, move_count=len(path))

        if remaining < self.best_score.remaining_count or \
                (remaining == self.best_score.remaining_count and len(path) < self.best_score.move_count):
            self.best_score = current_score
            self.best_sequence = list(path)

        if board_state in self.transposition_table:
            memoized = self.transposition_table[board_state]
            if memoized and not current_score.is_better_than(memoized):
                return

        self.transposition_table[board_state] = current_score
        legal_moves = Pathfinder.get_legal_moves(current_board)

        # Performance heuristic: prioritize closer matches
        legal_moves.sort(key=lambda m: abs(m.pos1.to_flat_index(BOARD_WIDTH) - m.pos2.to_flat_index(BOARD_WIDTH)))

        for move in legal_moves:
            next_board = current_board.apply_move(move)
            path.append(move)
            self._search(next_board, path)
            path.pop()


# ==========================================
# 4. STREAMLIT FRONTEND & INTERACTIVE UI
# ==========================================
st.set_page_config(page_title="Visual Number Match AI", layout="centered")

st.title("🧩 Visual Number Match AI Solver")
st.write("Upload your layout. The engine automatically handles row-collapsing slides up!")

uploaded_file = st.file_uploader("Upload Game Excel File (.xlsx)", type=["xlsx"])


def render_html_board(board_grid: List[List[int]], highlight_move: Optional[Move] = None) -> str:
    """Renders grid with highlighted target selectors."""
    html = "<div style='display: grid; grid-template-columns: repeat(9, 42px); gap: 6px; justify-content: center; margin-top: 15px; margin-bottom: 15px;'> wine"
    html = "<div style='display: grid; grid-template-columns: repeat(9, 42px); gap: 6px; justify-content: center;'>"

    for r in range(len(board_grid)):
        for c in range(BOARD_WIDTH):
            cell = board_grid[r][c]

            # Check if this cell is highlighted in the current step
            is_highlighted = False
            if highlight_move:
                if (r == highlight_move.pos1.row and c == highlight_move.pos1.col) or \
                        (r == highlight_move.pos2.row and c == highlight_move.pos2.col):
                    is_highlighted = True

            # Setup styles
            if cell == EMPTY_CELL:
                bg_color = "#f0f2f6"
                text_color = "#ccc"
                display_val = "•"
                border = "none"
            elif is_highlighted:
                bg_color = "#FFD700"  # Bright Gold/Yellow
                text_color = "#000"
                display_val = str(cell)
                border = "3px solid #FF4B4B"
            else:
                bg_color = "#4e8cff"  # Normal active cell Blue
                text_color = "white"
                display_val = str(cell)
                border = "none"

            html += f"<div style='width: 42px; height: 42px; background-color: {bg_color}; color: {text_color}; font-weight: bold; border-radius: 6px; display: flex; align-items: center; justify-content: center; border: {border}; font-size: 16px;'>{display_val}</div>"
    html += "</div>"
    return html


if uploaded_file is not None:
    wb = openpyxl.load_workbook(BytesIO(uploaded_file.read()), data_only=True)
    sheet = wb.active

    raw_grid = []
    for row in sheet.iter_rows(values_only=True):
        row_vals = []
        for i in range(BOARD_WIDTH):
            val = row[i] if i < len(row) else None
            if val is None or str(val).strip() in ("", "."):
                row_vals.append(EMPTY_CELL)
            else:
                try:
                    row_vals.append(int(val))
                except ValueError:
                    row_vals.append(EMPTY_CELL)
        raw_grid.append(row_vals)

    # Instantiate Initial State Board Configuration Matrix
    initial_board = Board(raw_grid)

    st.subheader("📋 Uploaded Starting Layout State")
    st.markdown(render_html_board(initial_board.grid), unsafe_allow_html=True)
    st.info(f"Active numbers detected: **{initial_board.get_remaining_numbers_count()}**")

    search_time = st.slider("Search Window Threshold (Seconds)", min_value=2, max_value=15, value=5)

    if "solution_steps" not in st.session_state:
        st.session_state.solution_steps = None
    if "initial_grids" not in st.session_state:
        st.session_state.initial_grids = None

    if st.button("🚀 Calculate Step-by-Step Guide", type="primary"):
        with st.spinner("Finding paths while simulating row collapses..."):
            solver = NumberMatchSolver(initial_board, max_seconds=float(search_time))
            moves_list = solver.solve()

            if moves_list:
                # Pre-calculate boards sequence states for manual playback steps
                grids_history = []
                temp_board = initial_board
                for mv in moves_list:
                    grids_history.append(temp_board.grid)
                    temp_board = temp_board.apply_move(mv)

                st.session_state.solution_steps = moves_list
                st.session_state.initial_grids = grids_history
            else:
                st.session_state.solution_steps = []
                st.session_state.initial_grids = []

    # Display Walkthrough Interface if solutions are loaded in cache memory
    if st.session_state.solution_steps is not None:
        if not st.session_state.solution_steps:
            st.error("No valid moves found within timeframe or left available on board layout.")
        else:
            st.success(
                f"Optimal chain found! Clears down to just {st.session_state.solution_steps[-1].value1 if len(st.session_state.solution_steps) == 0 else 'minimal'} remaining numbers.")

            st.write("---")
            st.subheader("🎯 Step-By-Step Interactive Player Guide")

            # Using standard slider configuration tracker to move through game frames manually
            step_idx = st.slider("Move Playback Selector", min_value=1, max_value=len(st.session_state.solution_steps),
                                 value=1)

            current_move = st.session_state.solution_steps[step_idx - 1]
            current_grid = st.session_state.initial_grids[step_idx - 1]

            st.markdown(f"### 📍 Step {step_idx} of {len(st.session_state.solution_steps)}")
            st.warning(
                f"👉 **Match the two YELLOW cells** showing values **{current_move.value1}** and **{current_move.value2}**!")

            # Draw the state frame with highlighted targeted coordinate locations
            st.markdown(render_html_board(current_grid, highlight_move=current_move), unsafe_allow_html=True)

            st.caption(
                "Notice: If a row becomes empty right after making this match, it disappears, shifting your mobile grid up to match the next step screen above!")