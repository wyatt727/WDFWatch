#!/usr/bin/env python3
"""
Batch processing utilities for efficient Claude API usage
"""

import logging
from typing import List, Callable, Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Utilities for batch processing tweets and responses.
    """
    
    def __init__(self, batch_size: int = 20, max_workers: int = 3):
        """
        Initialize batch processor.
        
        Args:
            batch_size: Items per batch
            max_workers: Maximum parallel workers
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        logger.info(f"Batch processor initialized (size={batch_size}, workers={max_workers})")
    
    def process_in_batches(self, 
                          items: List[Any], 
                          processor: Callable,
                          batch_mode: bool = True) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: Items to process
            processor: Function to process each batch/item
            batch_mode: If True, process in batches; if False, process individually
            
        Returns:
            Processed results
        """
        if not items:
            return []
        
        if batch_mode:
            return self._process_batched(items, processor)
        else:
            return self._process_individual(items, processor)
    
    def _process_batched(self, items: List[Any], processor: Callable) -> List[Any]:
        """Process items in batches."""
        results = []
        total_batches = (len(items) + self.batch_size - 1) // self.batch_size
        
        logger.info(f"Processing {len(items)} items in {total_batches} batches")
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            
            logger.debug(f"Processing batch {batch_num}/{total_batches}")
            
            try:
                batch_results = processor(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                # Add empty results for failed batch
                results.extend([None] * len(batch))
        
        return results
    
    def _process_individual(self, items: List[Any], processor: Callable) -> List[Any]:
        """Process items individually with parallelization."""
        results = [None] * len(items)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(processor, item): i 
                for i, item in enumerate(items)
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                    completed += 1
                    if completed % 10 == 0:
                        logger.debug(f"Processed {completed}/{len(items)} items")
                except Exception as e:
                    logger.error(f"Error processing item {index}: {e}")
                    results[index] = None
        
        return results
    
    def chunk_items(self, items: List[Any]) -> List[List[Any]]:
        """
        Split items into chunks.
        
        Args:
            items: Items to chunk
            
        Returns:
            List of chunks
        """
        chunks = []
        for i in range(0, len(items), self.batch_size):
            chunks.append(items[i:i+self.batch_size])
        return chunks
    
    def group_by_similarity(self, items: List[Dict], key: str = 'text') -> List[List[Dict]]:
        """
        Group items by similarity for better batching.
        Currently uses simple length-based grouping.
        
        Args:
            items: Items to group
            key: Dictionary key to use for grouping
            
        Returns:
            Grouped items
        """
        # Sort by length for now (simple heuristic)
        sorted_items = sorted(items, key=lambda x: len(str(x.get(key, ''))))
        
        # Create batches from sorted items
        return self.chunk_items(sorted_items)