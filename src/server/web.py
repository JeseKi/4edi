"""Web 子进程入口。"""

from __future__ import annotations

from loguru import logger
import uvicorn

from src.server.config import global_config
from src.server.logging_config import setup_logging


def main() -> None:
    setup_logging(process_role="web")
    logger.info("Fullstack Template Web 进程启动")
    uvicorn.run(
        "src.server.main:app",
        host="0.0.0.0",
        port=global_config.app.port,
        reload=False,
        log_level=global_config.logging.level.lower(),
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
