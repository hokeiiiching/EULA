"""
Table detection and column extraction from OCR results.

Invoices and POs typically contain tables with line items.
This module identifies table structures and maps columns
so we can reliably extract Quantity, Unit Price, Total, etc.

Design Decisions:
- Spatial clustering groups text blocks into rows
- Column detection uses horizontal alignment patterns
- Header detection identifies column names for semantic mapping
- Overlapping blocks are handled by center-point assignment
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .engine import OCRResult, TextBlock

logger = logging.getLogger(__name__)


# Tolerance for grouping items into the same row (as fraction of page height)
ROW_TOLERANCE = 0.015

# Tolerance for grouping items into the same column (as fraction of page width)
COLUMN_TOLERANCE = 0.05

# Minimum number of rows to be considered a table
MIN_TABLE_ROWS = 2


@dataclass
class TableCell:
    """A single cell in a detected table."""
    text: str
    confidence: float
    row: int
    column: int
    blocks: list[TextBlock] = field(default_factory=list)
    
    @property
    def min_confidence(self) -> float:
        """Minimum confidence among all blocks in this cell."""
        if not self.blocks:
            return self.confidence
        return min(b.confidence for b in self.blocks)


@dataclass
class TableRow:
    """A row of cells in a detected table."""
    index: int
    cells: dict[int, TableCell] = field(default_factory=dict)
    
    def get_cell(self, column: int) -> TableCell | None:
        """Get cell at specified column index."""
        return self.cells.get(column)
    
    def as_dict(self, column_names: dict[int, str]) -> dict[str, Any]:
        """Convert row to dictionary using column names as keys."""
        result = {}
        for col_idx, name in column_names.items():
            cell = self.cells.get(col_idx)
            if cell:
                result[name] = cell.text
        return result


@dataclass
class DetectedTable:
    """A table detected in the document."""
    page: int
    rows: list[TableRow]
    column_positions: list[float]  # X positions of column boundaries
    column_names: dict[int, str] = field(default_factory=dict)  # Column index -> name
    
    # Bounding region of the table
    x_min: float = 0
    y_min: float = 0
    x_max: float = 1
    y_max: float = 1
    
    @property
    def num_columns(self) -> int:
        """Number of columns in the table."""
        return len(self.column_positions) + 1
    
    @property
    def num_rows(self) -> int:
        """Number of rows in the table."""
        return len(self.rows)
    
    def get_column_by_name(self, name: str) -> int | None:
        """Find column index by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for col_idx, col_name in self.column_names.items():
            if name_lower in col_name.lower():
                return col_idx
        return None
    
    def iter_data_rows(self) -> list[TableRow]:
        """Iterate over data rows (excluding header row)."""
        if not self.rows:
            return []
        # Skip first row if it appears to be the header
        if self.column_names:
            return self.rows[1:]
        return self.rows


class TableDetector:
    """
    Detects tables and extracts structured data from OCR results.
    
    Uses spatial analysis to identify:
    1. Rows: Text blocks at similar vertical positions
    2. Columns: Text blocks at similar horizontal positions
    3. Headers: First row containing common column names
    
    Example:
        detector = TableDetector()
        tables = detector.detect_tables(ocr_result)
        for table in tables:
            for row in table.iter_data_rows():
                qty = row.get_cell(table.get_column_by_name("qty"))
    """
    
    # Common column name patterns for invoice tables
    COLUMN_PATTERNS = {
        "quantity": ["qty", "quantity", "units", "count", "pcs"],
        "description": ["description", "item", "product", "service", "particulars"],
        "unit_price": ["unit price", "price", "rate", "unit cost", "each"],
        "amount": ["amount", "total", "line total", "ext.", "extension"],
    }
    
    def __init__(
        self,
        row_tolerance: float = ROW_TOLERANCE,
        column_tolerance: float = COLUMN_TOLERANCE,
        min_rows: int = MIN_TABLE_ROWS,
    ) -> None:
        """
        Initialize table detector.
        
        Args:
            row_tolerance: Vertical tolerance for grouping rows (0-1)
            column_tolerance: Horizontal tolerance for grouping columns (0-1)
            min_rows: Minimum rows required to be considered a table
        """
        self.row_tolerance = row_tolerance
        self.column_tolerance = column_tolerance
        self.min_rows = min_rows
    
    def detect_tables(self, ocr_result: OCRResult) -> list[DetectedTable]:
        """
        Detect all tables in an OCR result.
        
        Args:
            ocr_result: OCR output with text blocks
            
        Returns:
            List of detected tables, sorted by page and vertical position
        """
        tables: list[DetectedTable] = []
        
        for page in ocr_result.pages:
            page_tables = self._detect_tables_on_page(page.blocks, page.page_number)
            tables.extend(page_tables)
        
        return tables
    
    def _detect_tables_on_page(
        self,
        blocks: list[TextBlock],
        page: int,
    ) -> list[DetectedTable]:
        """Detect tables on a single page."""
        if not blocks:
            return []
        
        # Group blocks into rows by vertical position
        rows = self._group_into_rows(blocks)
        
        if len(rows) < self.min_rows:
            return []
        
        # Find column boundaries from vertical alignment patterns
        column_positions = self._detect_column_boundaries(blocks)
        
        # Build table structure
        table_rows = self._build_table_rows(rows, column_positions)
        
        if not table_rows:
            return []
        
        # Detect header row and extract column names
        column_names = self._detect_header(table_rows[0], column_positions)
        
        # Calculate table bounds
        x_min = min(b.x_min for b in blocks)
        y_min = min(b.y_min for b in blocks)
        x_max = max(b.x_max for b in blocks)
        y_max = max(b.y_max for b in blocks)
        
        table = DetectedTable(
            page=page,
            rows=table_rows,
            column_positions=column_positions,
            column_names=column_names,
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
        )
        
        return [table]
    
    def _group_into_rows(
        self,
        blocks: list[TextBlock],
    ) -> list[list[TextBlock]]:
        """Group text blocks into rows based on vertical position."""
        if not blocks:
            return []
        
        # Sort by vertical position
        sorted_blocks = sorted(blocks, key=lambda b: b.center_y)
        
        rows: list[list[TextBlock]] = []
        current_row: list[TextBlock] = [sorted_blocks[0]]
        current_y = sorted_blocks[0].center_y
        
        for block in sorted_blocks[1:]:
            if abs(block.center_y - current_y) <= self.row_tolerance:
                current_row.append(block)
            else:
                rows.append(current_row)
                current_row = [block]
                current_y = block.center_y
        
        if current_row:
            rows.append(current_row)
        
        # Sort blocks within each row by horizontal position
        for row in rows:
            row.sort(key=lambda b: b.center_x)
        
        return rows
    
    def _detect_column_boundaries(
        self,
        blocks: list[TextBlock],
    ) -> list[float]:
        """
        Detect column boundaries from horizontal alignment patterns.
        
        Returns list of X positions that separate columns.
        """
        if not blocks:
            return []
        
        # Collect all left edges
        left_edges = [b.x_min for b in blocks]
        left_edges.sort()
        
        # Cluster left edges to find column starts
        column_starts: list[float] = []
        cluster_start = left_edges[0]
        cluster_sum = left_edges[0]
        cluster_count = 1
        
        for edge in left_edges[1:]:
            if edge - cluster_start <= self.column_tolerance:
                cluster_sum += edge
                cluster_count += 1
            else:
                # Found a new column
                if column_starts:
                    # The boundary is between previous cluster and this one
                    boundary = (column_starts[-1] + cluster_start) / 2 + self.column_tolerance
                    if boundary > column_starts[-1]:
                        column_starts.append(boundary)
                column_starts.append(cluster_sum / cluster_count)
                cluster_start = edge
                cluster_sum = edge
                cluster_count = 1
        
        # Handle last cluster
        if column_starts:
            column_starts.append(cluster_sum / cluster_count)
        else:
            column_starts.append(cluster_sum / cluster_count)
        
        # Convert column starts to boundaries between columns
        boundaries: list[float] = []
        for i in range(len(column_starts) - 1):
            boundary = (column_starts[i] + column_starts[i + 1]) / 2
            boundaries.append(boundary)
        
        return boundaries
    
    def _build_table_rows(
        self,
        text_rows: list[list[TextBlock]],
        column_positions: list[float],
    ) -> list[TableRow]:
        """Convert grouped text blocks into structured table rows."""
        table_rows: list[TableRow] = []
        
        for row_idx, blocks in enumerate(text_rows):
            cells: dict[int, TableCell] = {}
            
            for block in blocks:
                col_idx = self._get_column_index(block.center_x, column_positions)
                
                if col_idx in cells:
                    # Append to existing cell
                    cells[col_idx].text += " " + block.text
                    cells[col_idx].blocks.append(block)
                else:
                    # Create new cell
                    cells[col_idx] = TableCell(
                        text=block.text,
                        confidence=block.confidence,
                        row=row_idx,
                        column=col_idx,
                        blocks=[block],
                    )
            
            table_rows.append(TableRow(index=row_idx, cells=cells))
        
        return table_rows
    
    def _get_column_index(
        self,
        x_position: float,
        boundaries: list[float],
    ) -> int:
        """Determine which column a position belongs to."""
        for i, boundary in enumerate(boundaries):
            if x_position < boundary:
                return i
        return len(boundaries)
    
    def _detect_header(
        self,
        first_row: TableRow,
        column_positions: list[float],
    ) -> dict[int, str]:
        """
        Detect if first row is a header and extract column names.
        
        Returns mapping of column index to normalized column name.
        """
        column_names: dict[int, str] = {}
        
        for col_idx, cell in first_row.cells.items():
            text = cell.text.lower().strip()
            
            # Check against known patterns
            for canonical_name, patterns in self.COLUMN_PATTERNS.items():
                if any(p in text for p in patterns):
                    column_names[col_idx] = canonical_name
                    break
            else:
                # Use original text if no pattern matches
                column_names[col_idx] = text
        
        return column_names
    
    def find_quantity_column(self, table: DetectedTable) -> int | None:
        """Find the column containing quantity values."""
        return table.get_column_by_name("quantity")
    
    def find_amount_column(self, table: DetectedTable) -> int | None:
        """Find the column containing amount/total values."""
        return table.get_column_by_name("amount")
