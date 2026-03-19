import httpx
import time
import os
import sys
from typing import Optional

# Windows terminal UTF-8 support fix
if sys.platform == "win32":
    try:
        # For Python 3.7+
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older versions if needed
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())

# Rich implementation for colorful terminal output
try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# --- CONFIGURATION ---
BASE_URL = "https://your-render-service.onrender.com"
API_KEY = "CHANGE_ME" 
HEADERS = {"x-api-key": API_KEY}

# Console setup with safe encoding
if HAS_RICH:
    console = Console(force_terminal=True, soft_wrap=True)
else:
    class MockConsole:
        def print(self, msg, *args, **kwargs): print(msg)
    console = MockConsole()

# Endpoint list to test: (Name, Path, Needs Key)
ENDPOINTS = [
    ("Ping (Health Check)", "/ping", False),
    ("Stock Details (THYAO)", "/stocks/THYAO", True),
    ("Simulated Depth (THYAO)", "/stocks/THYAO/depth", True),
    ("KAP Disclosures (THYAO)", "/stocks/THYAO/disclosures", True),
    ("Fund Deep Scan (TLY)", "/funds/TLY/estimated-return", True),
    ("Market Breadth (A/D)", "/market/breadth", False),
    ("Market Heatmap", "/market/heatmap", False),
    ("Inflation Data", "/market/economy/inflation", False),
    ("TCMB Rates", "/market/economy/rates", False),
    ("Twitter Dynamic Auth Check", "/search/tweets?q=THYAO&limit=5", False),
    ("Global Search", "/search?q=THYAO", False),
]

def run_tests():
    if HAS_RICH:
        table = Table(title="[bold magenta]BorsaPy Ultimate API (v1.0.7) Health Report[/bold magenta]")
        table.add_column("Uç Nokta (Endpoint)", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Latency", justify="right")
        table.add_column("Result Hint", style="dim")
    else:
        print(f"\n--- BorsaPy Ultimate API Health Report ({BASE_URL}) ---\n")

    console.print(f"\n[bold blue]STARTING API TESTS: {BASE_URL}[/bold blue]\n")

    for name, path, needs_key in ENDPOINTS:
        url = f"{BASE_URL}{path}"
        start_time = time.time()
        
        try:
            req_headers = HEADERS if needs_key else {}
            response = httpx.get(url, headers=req_headers, timeout=30.0)
            latency = round(time.time() - start_time, 2)
            
            if response.status_code == 200:
                status = "[green]OK[/green]" if HAS_RICH else "OK"
                hint = "Success"
            elif response.status_code == 403:
                status = "[yellow]AUTH ERROR[/yellow]" if HAS_RICH else "AUTH ERROR"
                hint = "Check API_KEY"
            else:
                status = f"[red]FAIL ({response.status_code})[/red]" if HAS_RICH else f"FAIL ({response.status_code})"
                hint = f"Body: {response.text[:20]}"
                
        except Exception as e:
            latency = round(time.time() - start_time, 2)
            status = "[red]TIMEOUT/ERROR[/red]" if HAS_RICH else "ERROR"
            hint = str(e)[:40]

        if HAS_RICH:
            table.add_row(name, status, f"{latency}s", hint)
        else:
            print(f"{name:35} | {status:15} | {latency:6}s | {hint}")

    if HAS_RICH:
        console.print(table)
    
    console.print("\n[bold green]Tests Completed![/bold green]\n")

if __name__ == "__main__":
    run_tests()
