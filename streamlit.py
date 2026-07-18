import streamlit as st
import time
from typing import NamedTuple, List, Tuple, Optional

# ==========================================
# 1. CORE DATA STRUCTURES & CONFIG
# ==========================================
EMPTY_CELL = 0
TARGET_SUM = 10
BOARD_WIDTH = 9

class Position(NamedTuple):
    row: int
    col: int
    def to_flat_index(self, width: int) -> int: 
        return self.row * width + self.col

class Move(NamedTuple):
    pos1: Position
    pos2: Position
    value1: int
    value2: int

class Board:
    def __init__(self, grid: List[List[int]]):
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
        new_grid = [list(row) for row in self.grid]
        new_grid[move.pos1.row][move.pos1.col] = EMPTY_CELL
        new_grid[move.pos2.row][move.pos2.col] = EMPTY_CELL
        collapsed_grid = [row for row in new_grid if any(cell != EMPTY_CELL for cell in row)]
        return Board(collapsed_grid)

# ==========================================
# 2. OPTIMIZED SOLVER ENGINE
# ==========================================
class Pathfinder:
    @staticmethod
    def get_legal_moves(board: Board) -> List[Move]:
        moves = []
        grid = board.grid
        height = board.height
        width = board.width
        flat_positions = [Position(r, c) for r in range(height) for c in range(width)]

        last_pos: Optional[Position] = None
        for pos in flat_positions:
            val = grid[pos.row][pos.col]
            if val != EMPTY_CELL:
                if last_pos is not None:
                    last_val = grid[last_pos.row][last_pos.col]
                    if Pathfinder._is_valid_pair(last_val, val):
                        moves.append(Move(last_pos, pos, last_val, val))
                last_pos = pos

        directions = [(1, 0), (1, 1), (1, -1)]
        for r in range(height):
            for c in range(width):
                val1 = grid[r][c]
                if val1 == EMPTY_CELL: continue
                p1 = Position(r, c)
                for dr, dc in directions:
                    nr, nc = r + dr, c + dc
                    while 0 <= nr < height and 0 <= nc < width:
                        val2 = grid[nr][nc]
                        if val2 != EMPTY_CELL:
                            if Pathfinder._is_valid_pair(val1, val2):
                                moves.append(Move(p1, Position(nr, nc), val1, val2))
                            break
                        nr += dr
                        nc += dc
        return moves

    @staticmethod
    def _is_valid_pair(v1: int, v2: int) -> bool:
        return v1 == v2 or (v1 + v2) == TARGET_SUM

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

    def solve(self) -> List[Move]:
        self.start_time = time.time()
        self._search(self.initial_board, [])
        return self.best_sequence

    def _search(self, current_board: Board, path: List[Move]) -> None:
        if time.time() - self.start_time > self.max_seconds: return
        board_state = current_board.to_tuple()
        remaining = current_board.get_remaining_numbers_count()
        current_score = SolutionScore(remaining_count=remaining, move_count=len(path))

        if remaining < self.best_score.remaining_count or \
           (remaining == self.best_score.remaining_count and len(path) < self.best_score.move_count):
            self.best_score = current_score
            self.best_sequence = list(path)

        if board_state in self.transposition_table:
            memoized = self.transposition_table[board_state]
            if memoized and not current_score.is_better_than(memoized): return
        
        self.transposition_table[board_state] = current_score
        legal_moves = Pathfinder.get_legal_moves(current_board)
        legal_moves.sort(key=lambda m: abs(m.pos1.to_flat_index(BOARD_WIDTH) - m.pos2.to_flat_index(BOARD_WIDTH)))
        
        for move in legal_moves:
            next_board = current_board.apply_move(move)
            path.append(move)
            self._search(next_board, path)
            path.pop()

# ==========================================
# 3. HTML GRID UI RENDERER
# ==========================================
def render_html_board(board_grid: List[List[int]], highlight_move: Optional[Move] = None) -> str:
    html = "<div style='display: grid; grid-template-columns: repeat(9, 1fr); gap: 4px; max-width: 360px; margin: 10px auto;'>"
    for r in range(len(board_grid)):
        for c in range(BOARD_WIDTH):
            cell = board_grid[r][c]
            is_highlighted = False
            if highlight_move and ((r == highlight_move.pos1.row and c == highlight_move.pos1.col) or (r == highlight_move.pos2.row and c == highlight_move.pos2.col)):
                is_highlighted = True
            
            if cell == EMPTY_CELL:
                html += "<div style='aspect-ratio: 1; background-color: #f0f2f6; color: #ccc; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 14px;'>•</div>"
            elif is_highlighted:
                html += f"<div style='aspect-ratio: 1; background-color: #FFD700; color: #000; font-weight: bold; border-radius: 6px; display: flex; align-items: center; justify-content: center; border: 2px solid #FF4B4B; font-size: 15px;'>{cell}</div>"
            else:
                html += f"<div style='aspect-ratio: 1; background-color: #4e8cff; color: white; font-weight: bold; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 15px;'>{cell}</div>"
    html += "</div>"
    return html

# ==========================================
# 4. STREAMLIT APP FRONTEND
# ==========================================
st.set_page_config(page_title="Number Match Solver", layout="centered")

# CSS hack to force standard native grids to stay inline on mobile
st.markdown("""
    <style>
    div[data-testid="stColumn"] {
        flex: 1 1 0% !important;
        min-width: 0px !important;
        padding: 1px !important;
    }
    div[data-testid="column"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }
    input {
        text-align: center !important;
        padding: 4px !important;
        font-size: 16px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 Numner Match Solver")

if "num_rows" not in st.session_state:
    st.session_state.num_rows = 5

st.subheader("📝 Input Your Board Layout")

btn_col1, btn_col2 = st.columns(2)
with btn_col1:
    if st.button("➕ Add New Row", use_container_width=True):
        st.session_state.num_rows += 1
        st.rerun()

with btn_col2:
    if st.button("➖ Remove Last Row", use_container_width=True):
        if st.session_state.num_rows > 1:
            st.session_state.num_rows -= 1
            st.rerun()

current_input_grid = []
for r in range(st.session_state.num_rows):
    cols = st.columns(BOARD_WIDTH)
    row_vals = []
    for c in range(BOARD_WIDTH):
        # Using clear text input boxes optimized for mobile numeric keyboard pads
        val_input = cols[c].text_input(
            f"R{r}C{c}", 
            value="", 
            key=f"txt_{r}_{c}", 
            label_visibility="collapsed",
            placeholder="•"
        )
        if val_input.isdigit() and 1 <= int(val_input) <= 9:
            row_vals.append(int(val_input))
        else:
            row_vals.append(EMPTY_CELL)
    current_input_grid.append(row_vals)

st.write("---")
st.subheader("👁️ Current Matrix Preview")
st.markdown(render_html_board(current_input_grid), unsafe_allow_html=True)

search_time = st.slider("Search Computational Limit (Seconds)", min_value=2, max_value=15, value=5)

if "solution_steps" not in st.session_state:
    st.session_state.solution_steps = None
if "initial_grids" not in st.session_state:
    st.session_state.initial_grids = None
if "current_step_idx" not in st.session_state:
    st.session_state.current_step_idx = 0

if st.button("🚀 Find Winning Sequence", type="primary", use_container_width=True):
    initial_board = Board(current_input_grid)
    
    if initial_board.get_remaining_numbers_count() == 0:
        st.error("Please add data values to the grid before execution!")
    else:
        with st.spinner("Calculating optimal moves..."):
            solver = NumberMatchSolver(initial_board, max_seconds=float(search_time))
            moves_list = solver.solve()
            
            if moves_list:
                grids_history = []
                temp_board = initial_board
                for mv in moves_list:
                    grids_history.append(temp_board.grid)
                    temp_board = temp_board.apply_move(mv)
                st.session_state.solution_steps = moves_list
                st.session_state.initial_grids = grids_history
                st.session_state.current_step_idx = 0
            else:
                st.session_state.solution_steps = []
                st.session_state.initial_grids = []
                st.info("No solution sequence exists for this exact setup.")

if st.session_state.solution_steps:
    st.write("---")
    st.subheader("🎯 Step-By-Step Interactive Player Guide")
    
    total_steps = len(st.session_state.solution_steps)
    curr_idx = st.session_state.current_step_idx
    
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
    
    with nav_col1:
        if st.button("⏮️ Reset", use_container_width=True, disabled=(curr_idx == 0)):
            st.session_state.current_step_idx = 0
            st.rerun()
            
    with nav_col2:
        if st.button("⬅️ Previous", use_container_width=True, disabled=(curr_idx == 0)):
            st.session_state.current_step_idx -= 1
            st.rerun()
            
    with nav_col3:
        if st.button("Next ➡️", use_container_width=True, disabled=(curr_idx >= total_steps - 1)):
            st.session_state.current_step_idx += 1
            st.rerun()

    current_move = st.session_state.solution_steps[curr_idx]
    current_grid = st.session_state.initial_grids[curr_idx]
    
    st.markdown(f"### 📍 Step {curr_idx + 1} of {total_steps}")
    st.warning(f"👉 Match the two **YELLOW** cells showing **{current_move.value1}** and **{current_move.value2}**!")
    st.markdown(render_html_board(current_grid, highlight_move=current_move), unsafe_allow_html=True)
