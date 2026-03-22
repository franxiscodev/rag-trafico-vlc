"""
Scheduler de actualización del índice Qdrant.
Ejecuta el pipeline de ingesta cada 3 minutos usando APScheduler.

Uso standalone: uv run python -m ingesta.scheduler
(También es iniciado por el lifespan de FastAPI en app/main.py)
"""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from ingesta.embedder import run_ingesta

log = logging.getLogger(__name__)

INTERVALO_MINUTOS = 3


def _job() -> None:
    try:
        total = run_ingesta()
        log.info("Ciclo de ingesta completado: %d documentos.", total)
    except Exception as e:
        log.error("Error en ciclo de ingesta: %s", e)


def start_background_scheduler() -> BackgroundScheduler:
    """
    Inicia el scheduler en background.
    Usar desde el lifespan de FastAPI.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=INTERVALO_MINUTOS,
        id="ingesta_trafico",
        replace_existing=True,
    )
    scheduler.start()
    log.info("Scheduler iniciado: ingesta cada %d minutos.", INTERVALO_MINUTOS)
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Primera ingesta inmediata
    log.info("Ejecutando primera ingesta...")
    _job()

    # Luego scheduling periódico bloqueante
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=INTERVALO_MINUTOS,
        id="ingesta_trafico",
    )
    log.info("Scheduler activo. Proxima ejecucion en %d minutos. Ctrl+C para detener.", INTERVALO_MINUTOS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler detenido.")
