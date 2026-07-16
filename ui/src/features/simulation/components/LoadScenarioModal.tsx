// ui/src/features/simulation/components/LoadScenarioModal.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { X, Loader2, Database, Clock, Trash2 } from 'lucide-react';
import {
  ScenarioListItem,
  deleteScenarioFromDB,
} from '../../../api/simulation';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onLoad: (id: string) => void;
  fetchItems: () => Promise<ScenarioListItem[]>;
}

export function LoadScenarioModal({
  isOpen,
  onClose,
  onLoad,
  fetchItems,
}: Props) {
  const [items, setItems] = useState<ScenarioListItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 목록 새로고침 함수
  const loadList = useCallback(() => {
    setLoading(true);
    fetchItems().then((data) => {
      setItems(data);
      setLoading(false);
    });
  }, [fetchItems]);

  useEffect(() => {
    if (isOpen) {
      loadList();
    }
  }, [isOpen, loadList]);

  // 🚀 삭제 버튼 클릭 핸들러
  const handleDelete = async (
    e: React.MouseEvent,
    id: string,
    name: string,
  ) => {
    e.stopPropagation(); // 이거 없으면 1.삭제 2.불러오기 가 동시에 실행됨! 방어막 필수
    if (window.confirm(`'${name}' 시나리오를 정말 삭제하시겠습니까?`)) {
      try {
        await deleteScenarioFromDB(id);
        loadList(); // 삭제 성공하면 목록 새로고침!
      } catch (error) {
        console.error('Delete failed:', error);
        alert('삭제에 실패했습니다. 서버 연결을 확인해주세요.');
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/50">
          <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <Database className="w-4 h-4 text-sky-400" />
            저장된 시나리오 불러오기
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white rounded-md hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-2 flex-1 overflow-y-auto max-h-[60vh] min-h-[200px]">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-sky-500" />
              <span className="text-xs">데이터베이스 조회 중...</span>
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 text-xs gap-2 py-10">
              <Database className="w-8 h-8 opacity-20" />
              저장된 시나리오가 없습니다.
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => onLoad(item.id)}
                  className="group flex items-center justify-between p-3 rounded-lg border border-transparent hover:border-sky-500/50 hover:bg-sky-900/20 transition-all cursor-pointer text-left"
                >
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-slate-200">
                      {item.name}
                    </span>
                    <span className="text-[10px] text-slate-500 flex items-center gap-1 mt-1">
                      <Clock className="w-3 h-3" />
                      {new Date(
                        item.created_at.endsWith('Z')
                          ? item.created_at
                          : item.created_at + 'Z',
                      ).toLocaleString('ko-KR')}
                    </span>
                  </div>

                  {/* 🚀 빨간색 휴지통 아이콘 (마우스 올렸을 때만 선명하게 보이도록 UI 처리) */}
                  <button
                    onClick={(e) => handleDelete(e, item.id, item.name)}
                    className="p-2 text-slate-600 opacity-0 group-hover:opacity-100 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-all"
                    title="삭제"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
