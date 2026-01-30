// ui/src/components/Shell.tsx
import { ReactNode } from "react";

type NavKey = "builder";

export function Shell({
  active = "builder",
  onChange,
  children,
}: {
  active?: NavKey;
  onChange?: (k: NavKey) => void;
  children: ReactNode;
}) {
  return (
    // [최적화] 불필요한 패딩, 헤더, 푸터 모두 제거
    // 오직 자식 컴포넌트(FlowBuilderScreen)가 화면 전체를 쓰도록 허용
    <div className="flex flex-col w-full h-full bg-slate-950 text-slate-100">
      <div className="flex-1 w-full min-h-0">
        {children}
      </div>
    </div>
  );
}