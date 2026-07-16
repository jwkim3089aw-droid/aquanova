import sys
import os

# 현재 경로를 시스템 패스에 추가하여 app 모듈을 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models.scenario import Scenario


def clear_all_scenarios():
    db = SessionLocal()
    try:
        # Scenario 테이블의 모든 데이터 삭제
        deleted_count = db.query(Scenario).delete()
        db.commit()
        print("=" * 50)
        print(
            f"🧹 싹쓸이 완료! 총 {deleted_count}개의 시나리오가 DB에서 영구 삭제되었습니다."
        )
        print("=" * 50)
    except Exception as e:
        db.rollback()
        print(f"오류 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    clear_all_scenarios()
