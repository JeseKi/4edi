from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import FileAsset


class FileAssetDAO:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **values) -> FileAsset:
        asset = FileAsset(**values)
        self.db.add(asset)
        self.db.flush()
        return asset

    def get(self, asset_id: str) -> FileAsset | None:
        return self.db.get(FileAsset, asset_id)

    def list_for_user(
        self, *, user_id: int | None, offset: int, limit: int
    ) -> tuple[list[FileAsset], int]:
        statement = select(FileAsset).where(FileAsset.status == "available")
        count_statement = (
            select(func.count())
            .select_from(FileAsset)
            .where(FileAsset.status == "available")
        )
        if user_id is not None:
            statement = statement.where(FileAsset.created_by_user_id == user_id)
            count_statement = count_statement.where(FileAsset.created_by_user_id == user_id)
        total = int(self.db.scalar(count_statement) or 0)
        items = list(
            self.db.scalars(
                statement.order_by(FileAsset.created_at.desc()).offset(offset).limit(limit)
            )
        )
        return items, total
