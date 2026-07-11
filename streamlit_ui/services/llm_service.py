"""
LLM Service for Stock Screener
Handles natural language queries and AI-powered analysis using Ollama
"""

import json
import os
import re
import traceback
from typing import Any, Dict, List, Optional

import ollama
import streamlit as st
from loguru import logger


class LLMService:
    """Service for interacting with local LLM via Ollama"""

    def __init__(self, model: str = "phi3", base_url: Optional[str] = None):
        """
        Initialize LLM service

        Args:
            model: Model name to use (default: phi3)
            base_url: Custom Ollama base URL (default: http://localhost:11434)
        """
        self.model = model
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )

        # Test connection
        try:
            self._test_connection()
        except Exception as e:
            logger.warning(f"LLM service initialization warning: {e}")

    def _test_connection(self) -> bool:
        """Test connection to Ollama"""
        try:
            ollama.list()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            raise

    def interpret_screening_query(self, query: str) -> Dict[str, Any]:
        """
        Interpret natural language screening query into structured criteria.

        Returns a dict with keys:
          sector, industry, min_price, max_price, min_volume, min_market_cap,
          rsi_min, rsi_max, min_price_change_pct, max_price_change_pct,
          keywords, sort_by (one of: rsi_desc, rsi_asc, price_change_desc,
          price_change_asc, market_cap_desc, price_desc, None)
        """
        prompt = f"""You are a financial analysis assistant.
Parse this stock screening query into structured criteria.

Query: "{query}"

Return ONLY a JSON object with these fields (use null for fields not mentioned):
{{
  "sector": string or null,
  "industry": string or null,
  "min_price": float or null,
  "max_price": float or null,
  "min_volume": int or null,
  "min_market_cap": float or null,
  "rsi_min": float or null,
  "rsi_max": float or null,
  "min_price_change_pct": float or null,
  "max_price_change_pct": float or null,
  "keywords": list of strings or null,
  "sort_by": string or null
}}

Rules:
1. Sector names: "Financial Services" (finance/bank),
   "Technology" (tech/software), "Healthcare" (health/medical),
   "Energy" (oil/gas), "Consumer Cyclical", "Consumer Defensive",
   "Industrials", "Basic Materials", "Real Estate",
   "Communication Services", "Utilities"
2. For "highest RSI" / "top RSI" / "most overbought"
   -> sort_by = "rsi_desc", leave rsi_min/rsi_max null
3. For "lowest RSI" / "most oversold"
   -> sort_by = "rsi_asc", leave rsi_min/rsi_max null
4. For "best performers" / "highest gain"
   -> sort_by = "price_change_desc"
5. For "worst performers" / "biggest losers"
   -> sort_by = "price_change_asc"
6. For "largest companies" / "biggest market cap"
   -> sort_by = "market_cap_desc"
7. Do NOT put sector names or sorting terms in keywords
8. keywords is ONLY for company name or ticker symbol searches

Examples:
Query: "find finance stocks with highest rsi"
{{"sector": "Financial Services", "sort_by": "rsi_desc", "keywords": null}}

Query: "Find tech stocks with RSI below 30 and price above 50"
{{"sector": "Technology", "rsi_max": 30, "min_price": 50, "sort_by": null}}

Query: "Show me Apple stock"
{{"keywords": ["Apple"], "sort_by": null}}

Query: "best performing healthcare stocks this month"
{{"sector": "Healthcare", "sort_by": "price_change_desc", "keywords": null}}
"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.1},
            )

            content = response["message"]["content"].strip()

            # Strip markdown fences if the model added them anyway
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            try:
                criteria = json.loads(content)
            except json.JSONDecodeError as json_err:
                logger.warning(
                    f"JSON parse error (fallback to regex): {json_err}"
                )
                criteria = self._fallback_parse(content)

            # Remove null values for cleaner downstream handling
            criteria = {k: v for k, v in criteria.items() if v is not None}

            # Correct comparison direction using the raw query text
            criteria = self._fix_comparison_direction(query, criteria)

            # Drop hallucinated keywords not present in the original query
            if "keywords" in criteria:
                q_lower = query.lower()
                criteria["keywords"] = [
                    kw for kw in criteria["keywords"]
                    if kw.lower() in q_lower
                ]
                if not criteria["keywords"]:
                    del criteria["keywords"]

            logger.info(f"Parsed query '{query}' -> criteria: {criteria}")
            return criteria

        except Exception as e:
            logger.error(f"Error interpreting query: {e}")
            logger.debug(traceback.format_exc())
            return {}

    def _fix_comparison_direction(
        self, query: str, criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Correct RSI/price comparison direction by re-reading the raw query.

        LLMs occasionally swap rsi_min/rsi_max or min_price/max_price.
        This method uses simple regex to detect explicit '<' / '>' / 'below' /
        'above' constructs and enforces the right field.
        """
        q = query.lower()

        # Patterns: "rsi < 30", "rsi below 30", "rsi under 30"  -> rsi_max
        #           "rsi > 70", "rsi above 70", "rsi over 70"   -> rsi_min
        rsi_upper = re.search(
            r'\brsi\b\s*(?:<|<=|below|under|less\s+than)\s*(\d+(?:\.\d+)?)', q
        )
        rsi_lower = re.search(
            r'\brsi\b\s*(?:>|>=|above|over|greater\s+than)\s*(\d+(?:\.\d+)?)', q
        )

        if rsi_upper:
            val = float(rsi_upper.group(1))
            criteria.pop("rsi_min", None)
            criteria["rsi_max"] = val
        if rsi_lower:
            val = float(rsi_lower.group(1))
            criteria.pop("rsi_max", None)
            criteria["rsi_min"] = val

        # price < X -> max_price; price > X -> min_price
        price_upper = re.search(
            r'\bprice\b\s*(?:<|<=|below|under|less\s+than)\s*(\d+(?:\.\d+)?)', q
        )
        price_lower = re.search(
            r'\bprice\b\s*(?:>|>=|above|over|greater\s+than)\s*(\d+(?:\.\d+)?)', q
        )

        if price_upper:
            val = float(price_upper.group(1))
            criteria.pop("min_price", None)
            criteria["max_price"] = val
        if price_lower:
            val = float(price_lower.group(1))
            criteria.pop("max_price", None)
            criteria["min_price"] = val

        return criteria

    def _fallback_parse(self, content: str) -> Dict[str, Any]:
        """Regex-based fallback for malformed JSON responses."""
        criteria: Dict[str, Any] = {}

        sector_m = re.search(
            r'"sector"\s*:\s*"([^"]+)"', content, re.IGNORECASE
        )
        if sector_m:
            criteria["sector"] = sector_m.group(1)

        numeric_fields = (
            "rsi_max", "rsi_min", "min_price", "max_price",
            "min_volume", "min_market_cap",
        )
        for field in numeric_fields:
            m = re.search(
                rf'"{field}"\s*:\s*(\d+(?:\.\d+)?)', content, re.IGNORECASE
            )
            if m:
                criteria[field] = float(m.group(1))

        sort_m = re.search(
            r'"sort_by"\s*:\s*"([^"]+)"', content, re.IGNORECASE
        )
        if sort_m:
            criteria["sort_by"] = sort_m.group(1)

        kw_m = re.search(
            r'"keywords"\s*:\s*\[(.*?)\]',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if kw_m:
            keywords = [
                kw.strip().strip("'\"")
                for kw in kw_m.group(1).split(",")
                if kw.strip()
            ]
            if keywords:
                criteria["keywords"] = keywords

        logger.info(f"Fallback-parsed criteria: {criteria}")
        return criteria

    def analyze_screened_results(
        self,
        results: List[Dict[str, Any]],
        query: Optional[str] = None,
    ) -> str:
        """
        Generate AI analysis of screened stock results,
        referencing specific stocks.
        """
        if not results:
            return "No stocks matched the screening criteria."

        # Build a compact data block for the top 10 results
        top_n = results[:10]
        stock_lines = []
        for s in top_n:
            rsi = s.get("rsi")
            price = s.get("current_price")
            chg30 = s.get("price_change_30d")
            macd_h = s.get("macd_histogram") or s.get("macd")
            bb = s.get("bb_position")

            if macd_h is not None:
                macd_dir = "bullish MACD" if macd_h > 0 else "bearish MACD"
            else:
                macd_dir = ""
            rsi_label = f"RSI {rsi:.0f}" if rsi is not None else ""
            chg_label = f"{chg30:+.1f}% 30d" if chg30 is not None else ""
            price_label = f"${price:.2f}" if price is not None else ""
            bb_label = f"BB pos {bb:.2f}" if bb is not None else ""

            raw = [
                s.get("symbol", "?"), s.get("name", ""),
                s.get("sector", ""), price_label,
                rsi_label, chg_label, macd_dir, bb_label,
            ]
            stock_lines.append("  - " + " | ".join(p for p in raw if p))

        stock_block = "\n".join(stock_lines)

        prompt = f"""You are a financial analyst.
Analyze these stock screening results and provide specific,
actionable insights.

Original query: {query or 'General screening'}
Total matches: {len(results)}

Top results:
{stock_block}

Provide a focused analysis (3-4 sentences) that:
1. References specific stocks by ticker/name from the data above
2. Highlights notable RSI levels, MACD signals, or price trends
3. Identifies the most interesting opportunity or risk in the set
4. Is concise and professional - no generic filler

Do not repeat the data back. Provide genuine interpretation.
"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7},
            )
            return response["message"]["content"].strip()

        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            return (
                f"Found {len(results)} stocks matching your criteria."
                " Review the table below for details."
            )

    def chat_about_results(
        self,
        results: List[Dict[str, Any]],
        history: List[Dict[str, str]],
        question: str,
    ) -> str:
        """
        Answer a follow-up question about screened results,
        maintaining conversation context.

        Args:
            results: The screened stock results (context for system message)
            history: Previous conversation turns [{role, content}, ...]
            question: The new user question

        Returns:
            Assistant response string
        """
        # Build a compact context string from results
        context_lines = []
        for s in results[:15]:
            rsi = s.get("rsi")
            macd_h = s.get("macd_histogram") or s.get("macd")
            chg30 = s.get("price_change_30d")
            macd_val = "bull" if (macd_h or 0) > 0 else "bear"
            parts = [
                s.get("symbol", "?"),
                s.get("name", ""),
                s.get("sector", ""),
                f"RSI={rsi:.0f}" if rsi is not None else "",
                f"MACD={macd_val}" if macd_h is not None else "",
                f"30d={chg30:+.1f}%" if chg30 is not None else "",
                f"${s.get('current_price', 0):.2f}"
                if s.get("current_price") else "",
            ]
            context_lines.append(" ".join(p for p in parts if p))

        context = "\n".join(context_lines)

        system_msg = {
            "role": "system",
            "content": (
                "You are a financial analysis assistant. "
                "The user is asking about these screened stocks:"
                f"\n{context}\n\n"
                "Answer questions concisely using the data above."
                " Reference specific tickers when relevant."
            ),
        }

        # Keep last 6 turns (3 exchanges) of history to avoid context bloat
        trimmed_history = history[-6:] if len(history) > 6 else history

        messages = (
            [system_msg]
            + trimmed_history
            + [{"role": "user", "content": question}]
        )

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={"temperature": 0.7},
            )
            return response["message"]["content"].strip()

        except Exception as e:
            logger.error(f"Error in chat_about_results: {e}")
            return "Sorry, I couldn't process that question. Please try again."

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available local Ollama models."""
        try:
            models = ollama.list()
            model_list = []

            if hasattr(models, "models"):
                for model in models.models:
                    if hasattr(model, "model"):
                        model_list.append(
                            {
                                "name": model.model.split(":")[0],
                                "full_name": model.model,
                                "size": getattr(model, "size", 0),
                            }
                        )

            return {"available_models": model_list, "current_model": self.model}
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {"available_models": [], "current_model": self.model}


@st.cache_resource
def get_llm_service(model: str = "phi3") -> LLMService:
    """Get or create a cached LLM service instance (one per session)."""
    return LLMService(model=model)
