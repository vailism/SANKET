import os
import pandas as pd
import pyarrow.dataset as ds
import pyarrow as pa
from typing import List, Dict, Optional, Any, Tuple

class DatasetReader:
    """
    Abstracts reads from the Hive-partitioned dataset architecture.
    """
    def __init__(self, base_dir: str = "DATA/datasets/LATEST"):
        self.base_dir = base_dir
        self.index_path = os.path.join(self.base_dir, "project_index.parquet")
        self._index_df = None

    @property
    def index(self) -> pd.DataFrame:
        if self._index_df is None:
            if os.path.exists(self.index_path):
                self._index_df = pd.read_parquet(self.index_path)
            else:
                self._index_df = pd.DataFrame()
        return self._index_df

    def _get_dataset_path(self, name: str) -> str:
        return os.path.join(self.base_dir, name)

    def read_dataset(self, name: str, columns: Optional[List[str]] = None, lazy: bool = False) -> Any:
        """
        Reads the full dataset. Returns a pyarrow dataset if lazy=True, else a pandas DataFrame.
        """
        path = self._get_dataset_path(name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset {name} not found at {path}")
            
        dataset = ds.dataset(path, format="parquet", partitioning="hive")
        if lazy:
            return dataset
        return dataset.to_table(columns=columns).to_pandas()

    def read_project(self, name: str, project_id: str, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Efficiently reads all rows for a specific project by using the project_index
        to load only the required partitions.
        """
        idx = self.index
        if idx.empty:
            # Fallback if no index: scan everything
            dataset = self.read_dataset(name, lazy=True)
            table = dataset.to_table(columns=columns, filter=ds.field("project_id") == project_id)
            return table.to_pandas()
            
        project_parts = idx[idx["project_id"] == project_id]
        if project_parts.empty:
            return pd.DataFrame()
            
        dataset_path = self._get_dataset_path(name)
        
        # Build list of specific partition directory paths to load
        # Wait, if name is a portfolio dataset, it only has sector_clean
        # We can just build a filter expression and pass it to pyarrow, 
        # PyArrow will use it to prune partitions automatically if it's on partition keys!
        
        sectors = project_parts["sector_clean"].unique().tolist()
        years = project_parts["reporting_year"].unique().tolist()
        
        dataset = ds.dataset(dataset_path, format="parquet", partitioning="hive")
        
        # PyArrow dataset filter pushdown is very efficient. 
        # If we filter by sector_clean and reporting_year, it won't read other files.
        # However, to be absolutely precise for project temporal fetching:
        filter_expr = ds.field("project_id") == project_id
        
        # We can speed up partition discovery by adding partition filters
        if "sector_clean" in dataset.schema.names:
            filter_expr = filter_expr & ds.field("sector_clean").isin(sectors)
        if "reporting_year" in dataset.schema.names:
            filter_expr = filter_expr & ds.field("reporting_year").isin(years)
            
        table = dataset.to_table(columns=columns, filter=filter_expr)
        return table.to_pandas()

    def read_partitions(self, name: str, filters: Dict[str, List[str]], columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Loads specific partitions defined by filters (e.g. {"sector_clean": ["Power"], "reporting_year": ["2024"]})
        """
        path = self._get_dataset_path(name)
        if not os.path.exists(path):
            return pd.DataFrame()
            
        dataset = ds.dataset(path, format="parquet", partitioning="hive")
        
        expr = None
        for col, values in filters.items():
            if col in dataset.schema.names:
                col_expr = ds.field(col).isin(values)
                expr = col_expr if expr is None else expr & col_expr
                
        if expr is None:
            return self.read_dataset(name, columns=columns, lazy=False)
            
        return dataset.to_table(columns=columns, filter=expr).to_pandas()

    def write_partitions(self, name: str, df: pd.DataFrame, partition_cols: List[str], base_dir: Optional[str] = None):
        """
        Writes a dataframe to a partitioned dataset.
        Usually used during incremental staging to write specific updated partitions.
        """
        out_dir = base_dir if base_dir else self._get_dataset_path(name)
        os.makedirs(out_dir, exist_ok=True)
        
        table = pa.Table.from_pandas(df)
        
        # Extract schema for partition columns
        schema_fields = []
        for col in partition_cols:
            schema_fields.append((col, pa.string()))
        part = ds.partitioning(schema=pa.schema(schema_fields), flavor="hive")
        
        ds.write_dataset(
            data=table,
            base_dir=out_dir,
            format="parquet",
            partitioning=part,
            existing_data_behavior="delete_matching"
        )
