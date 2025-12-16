import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class EventCache:
    """
    Central cache for all events from all sources.
    Stores full event data but provides minimal data for LLM processing.
    """
    
    def __init__(self):
        self.events: Dict[str, dict] = {}  # event_id -> full event data
        self.last_refresh: Dict[str, datetime] = {}  # source -> last refresh time
        self.ttl_seconds = 36000  # 10 hours
    
    def _generate_id(self, name: str, source: str) -> str:
        """Generate unique ID for an event."""
        key = f"{source}:{name}".lower()
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    def add_event(self, event: dict, source: str) -> str:
        """
        Add an event to the cache.
        
        Args:
            event: Full event data with all fields
            source: Source name (eventbrite, brussels, ticketmaster)
        
        Returns:
            str: Event ID
        """
        event_id = self._generate_id(event.get('name', ''), source)
        self.events[event_id] = {
            **event,
            '_id': event_id,
            '_source': source,
            '_cached_at': datetime.now().isoformat()
        }
        return event_id
    
    def get_event(self, event_id: str) -> Optional[dict]:
        """Get full event data by ID."""
        return self.events.get(event_id)
    
    def find_event_by_name(self, name: str, fuzzy: bool = True) -> Optional[dict]:
        """
        Find event by name (exact or fuzzy match).
        Used to match LLM's chosen events back to full data.
        """
        name_lower = name.lower().strip()
        
        # Exact match first
        for event in self.events.values():
            if event.get('name', '').lower().strip() == name_lower:
                return event
        
        # Fuzzy match: check if name contains or is contained
        if fuzzy:
            for event in self.events.values():
                event_name = event.get('name', '').lower()
                # Check both directions for partial match
                if name_lower in event_name or event_name in name_lower:
                    return event
                # Check first 30 chars (handles truncated names)
                if name_lower[:30] == event_name[:30]:
                    return event
        
        return None
    
    def get_llm_summary(self, source: str = None, limit: int = 50) -> str:
        """
        Get lightweight event summary for LLM (name + date + short description only).
        
        🌱 This saves ~60% tokens compared to sending full data!
        
        Args:
            source: Filter by source (optional)
            limit: Max events to include
        
        Returns:
            str: Compact text format for LLM
        """
        lines = []
        count = 0
        
        for event_id, event in self.events.items():
            if source and event.get('_source') != source:
                continue
            if count >= limit:
                break
            
            name = event.get('name', 'Unknown')
            date = event.get('date') or event.get('date_start', 'Date inconnue')
            # Truncate description to 100 chars for LLM
            desc = (event.get('description', '') or '')[:100]
            
            lines.append(f"[{event_id}] {name} | {date} | {desc}")
            count += 1
        
        return "\n".join(lines)
    
    def get_events_by_source(self, source: str) -> List[dict]:
        """Get all events from a specific source."""
        return [e for e in self.events.values() if e.get('_source') == source]
    
    def clear(self, source: str = None):
        """Clear cache (all or by source)."""
        if source:
            self.events = {k: v for k, v in self.events.items() if v.get('_source') != source}
        else:
            self.events = {}
    
    def stats(self) -> dict:
        """Get cache statistics."""
        sources = {}
        for event in self.events.values():
            src = event.get('_source', 'unknown')
            sources[src] = sources.get(src, 0) + 1
        
        return {
            'total_events': len(self.events),
            'by_source': sources,
            'memory_estimate_kb': len(str(self.events)) / 1024
        }


# Global cache instance
event_cache = EventCache()