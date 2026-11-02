"""Safe shadow-mode runtime for the modular-monolith preview.

Only public market data and read-only eth_call are used. No wallet, private key,
approval, order placement, or swap submission is loaded by this entry point.
"""
import argparse
import asyncio
import logging

from dotenv import load_dotenv

from arbitrage_bot.cells.cex.kucoin.market_data import KuCoinMarketData
from arbitrage_bot.cells.dexes.plunderswap.market_data import PlunderSwapMarketData
from arbitrage_bot.cells.networks.zilliqa_evm.read_only_rpc import ReadOnlyRPC
from arbitrage_bot.infrastructure.config import Settings
from arbitrage_bot.infrastructure.logging import configure_logging
from arbitrage_bot.services.market_data import MarketDataService
from arbitrage_bot.services.shadow_analyzer import ShadowAnalyzer
from arbitrage_bot.services.shadow_risk import ShadowRiskManager


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the arbitrage refactor in safe read-only shadow mode.")
    parser.add_argument("--cycles", type=int, default=None, help="Number of cycles; 1 runs a single snapshot. 0 means continuous.")
    parser.add_argument("--interval", type=float, default=None, help="Seconds between snapshots (minimum 1).")
    return parser.parse_args()


async def _run(settings: Settings, cycles: int, interval: float) -> int:
    # Import only configuration/ABI data from the legacy root module.
    # The legacy trading module and wallet/signing code are never imported.
    import constants as legacy_config

    rpc = ReadOnlyRPC(list(legacy_config.RPC_NODES), timeout_seconds=settings.rpc_timeout_seconds)
    kucoin = KuCoinMarketData(legacy_config.KUCOIN_BASE_URL, settings.kucoin_timeout_seconds)
    plunderswap = PlunderSwapMarketData(rpc, legacy_config)
    market_data = MarketDataService(kucoin, plunderswap, legacy_config)
    analyzer = ShadowAnalyzer(legacy_config)
    risk_manager = ShadowRiskManager()

    log = logging.getLogger("arbitrage_bot.runtime")
    log.warning("runtime_start mode=shadow live_trading_enabled=false cycles=%s interval_seconds=%s", cycles, interval)
    log.warning("safety_boundary read_only_rpc=true public_kucoin_data=true order_submission=disabled")
    completed = 0
    successful = 0
    failed = 0
    while cycles == 0 or completed < cycles:
        completed += 1
        try:
            snapshot = await market_data.collect()
            candidates = analyzer.analyze(snapshot)
            decisions = [(candidate, risk_manager.evaluate(candidate, snapshot)) for candidate in candidates]
            allowed = [(candidate, decision) for candidate, decision in decisions if decision.allowed]
            rejected = [(candidate, decision) for candidate, decision in decisions if not decision.allowed]
            for candidate, decision in rejected:
                log.info("shadow_risk_rejected pair=%s direction=%s reasons=%s",
                         candidate.pair, candidate.direction, ",".join(decision.reasons))
            for candidate, _decision in allowed:
                log.info("shadow_risk_allowed pair=%s direction=%s level=%d profit=%s threshold=%s",
                         candidate.pair, candidate.direction, candidate.level_index,
                         candidate.estimated_profit_quote, candidate.required_threshold)
            log.info(
                "shadow_cycle_complete cycle=%d observed_at=%s pairs=%d candidates=%d risk_allowed=%d risk_rejected=%d top_candidate=%s",
                completed, snapshot.observed_at.isoformat(), len(snapshot.plunderswap),
                len(candidates), len(allowed), len(rejected),
                (f"{allowed[0][0].pair}:{allowed[0][0].direction}:profit={allowed[0][0].estimated_profit_quote}"
                 if allowed else "none"),
            )
            successful += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            failed += 1
            log.exception("shadow_cycle_failed cycle=%d", completed)
        if cycles != 0 and completed >= cycles:
            break
        await asyncio.sleep(interval)
    log.warning("runtime_stopped mode=shadow cycles_completed=%d successful=%d failed=%d live_trading_enabled=false",
                completed, successful, failed)
    # A one-cycle smoke test must fail visibly when no data cycle succeeded.
    return 1 if successful == 0 else 0


def main() -> int:
    load_dotenv()
    args = _arguments()
    try:
        settings = Settings.from_env()
        cycles = settings.max_cycles if args.cycles is None else args.cycles
        interval = settings.check_interval_seconds if args.interval is None else args.interval
        if cycles < 0:
            raise ValueError("--cycles must be >= 0")
        if interval < 1:
            raise ValueError("--interval must be >= 1 second")
        configure_logging(settings.log_directory, settings.log_level)
        return asyncio.run(_run(settings, cycles, interval))
    except KeyboardInterrupt:
        logging.getLogger("arbitrage_bot.runtime").warning("runtime_interrupted")
        return 130
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("arbitrage_bot.runtime").exception("runtime_start_failed error=%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
