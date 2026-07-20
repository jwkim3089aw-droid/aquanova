// ui/src/features/simulation/results/pdf/usePdfExport.tsx
import {
  useCallback,
  useState,
} from 'react';

import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

const A4_WIDTH_MM = 210;
const A4_HEIGHT_MM = 297;

const captureOptions = {
  scale: 2,
  useCORS: true,
  logging: false,
  backgroundColor: '#ffffff',
  scrollY: -window.scrollY,
};

function waitForStableLayout(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        resolve();
      });
    });
  });
}

/*
 * Reports.tsx DOM:
 *
 * #report-viewer-content
 *   └─ report wrapper
 *       └─ ReportTemplate root
 *           ├─ Page 1
 *           ├─ Page 2
 *           ├─ Page 3
 *           ├─ Stage detail page
 *           └─ History page
 *
 * ReportTemplate root의 직접 자식만 가져오면 화면용 페이지 간격은
 * 제외되고 실제 논리적 리포트 페이지만 얻을 수 있다.
 */
function findLogicalReportPages(
  input: HTMLElement,
): HTMLElement[] {
  const reportWrapper =
    input.firstElementChild;

  if (!(reportWrapper instanceof HTMLElement)) {
    return [];
  }

  const reportRoot =
    reportWrapper.firstElementChild;

  if (!(reportRoot instanceof HTMLElement)) {
    return [];
  }

  return Array.from(
    reportRoot.children,
  ).filter(
    (child): child is HTMLElement => {
      if (!(child instanceof HTMLElement)) {
        return false;
      }

      const rect =
        child.getBoundingClientRect();

      return (
        rect.width > 0
        && rect.height > 0
      );
    },
  );
}

function addCanvasAsSinglePage(
  pdf: jsPDF,
  canvas: HTMLCanvasElement,
  pageIndex: number,
): void {
  if (pageIndex > 0) {
    pdf.addPage();
  }

  /*
   * 논리적 Page가 A4보다 아주 조금 커져도 잘리지 않도록
   * 가로·세로 중 더 제한적인 비율에 맞춘다.
   */
  const scaleMmPerPixel = Math.min(
    A4_WIDTH_MM / canvas.width,
    A4_HEIGHT_MM / canvas.height,
  );

  const imageWidth =
    canvas.width * scaleMmPerPixel;

  const imageHeight =
    canvas.height * scaleMmPerPixel;

  const x =
    (A4_WIDTH_MM - imageWidth) / 2;

  const imageData =
    canvas.toDataURL('image/png');

  pdf.addImage(
    imageData,
    'PNG',
    x,
    0,
    imageWidth,
    imageHeight,
    undefined,
    'FAST',
  );
}

/*
 * 예외적인 비-리포트 DOM을 위한 기존 방식의 fallback.
 * 정식 Reports 화면은 findLogicalReportPages 경로를 사용한다.
 */
async function addFallbackLongCanvas(
  pdf: jsPDF,
  input: HTMLElement,
): Promise<void> {
  const canvas = await html2canvas(
    input,
    captureOptions,
  );

  const imageData =
    canvas.toDataURL('image/png');

  const imageHeight =
    (
      canvas.height
      * A4_WIDTH_MM
    ) / canvas.width;

  let heightLeft = imageHeight;
  let position = 0;
  let pageIndex = 0;

  while (heightLeft > 0.5) {
    if (pageIndex > 0) {
      pdf.addPage();
    }

    pdf.addImage(
      imageData,
      'PNG',
      0,
      position,
      A4_WIDTH_MM,
      imageHeight,
      undefined,
      'FAST',
    );

    heightLeft -= A4_HEIGHT_MM;
    position -= A4_HEIGHT_MM;
    pageIndex += 1;
  }
}

export function usePdfExport() {
  const [
    isExporting,
    setIsExporting,
  ] = useState(false);

  const exportToPdf = useCallback(
    async (
      elementId: string,
      fileName: string = 'report.pdf',
    ) => {
      const input =
        document.getElementById(elementId);

      if (!input) {
        console.error(
          `Element with id ${elementId} not found`,
        );
        return;
      }

      const originalTransform =
        input.style.transform;

      const originalTransformOrigin =
        input.style.transformOrigin;

      try {
        setIsExporting(true);

        /*
         * 화면 확대/축소 상태가 PDF 해상도와 페이지 크기에
         * 영향을 주지 않도록 캡처 중에만 제거한다.
         */
        input.style.transform = 'none';
        input.style.transformOrigin =
          'top left';

        if (document.fonts?.ready) {
          await document.fonts.ready;
        }

        await waitForStableLayout();

        const pdf = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
        });

        const logicalPages =
          findLogicalReportPages(input);

        if (logicalPages.length > 0) {
          for (
            let index = 0;
            index < logicalPages.length;
            index += 1
          ) {
            const pageCanvas =
              await html2canvas(
                logicalPages[index],
                captureOptions,
              );

            addCanvasAsSinglePage(
              pdf,
              pageCanvas,
              index,
            );
          }
        } else {
          await addFallbackLongCanvas(
            pdf,
            input,
          );
        }

        pdf.save(fileName);
      } catch (err) {
        console.error(
          'PDF Export failed:',
          err,
        );

        alert('Failed to export PDF.');
      } finally {
        input.style.transform =
          originalTransform;

        input.style.transformOrigin =
          originalTransformOrigin;

        setIsExporting(false);
      }
    },
    [],
  );

  return {
    exportToPdf,
    isExporting,
  };
}
