# -*- coding: utf-8 -*-
"""
数据库访问对象（DAO）基类（模板版）

公开接口：
- `BaseDAO`：DAO 基类，持有 `db_session`

内部方法：
- 无

说明：
- Session 仅由 DatabaseExecutor 或 task runtime 创建；DAO 只在其同步回调中使用。
"""

from sqlalchemy.orm import Session


class BaseDAO:
    """DAO 基类"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
