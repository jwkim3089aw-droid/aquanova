// ui/src/features/simulation/results/pdf/usePdfExport.tsx
import { useCallback, useState } from 'react';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

export function usePdfExport() {
  const [isExporting, setIsExporting] = useState(false);

  const exportToPdf = useCallback(
    async (elementId: string, fileName: string = 'report.pdf') => {
      const input = document.getElementById(elementId);
      if (!input) {
        console.error(`Element with id ${elementId} not found`);
        return;
      }

      try {
        setIsExporting(true);

        // 1) Capture
        const canvas = await html2canvas(input, {
          scale: 2,
          useCORS: true,
          logging: false,
          backgroundColor: '#ffffff',
          scrollY: -window.scrollY, // ✅ 스크롤 위치 영향 줄이기
        });

        // 2) PDF
        const imgData = canvas.toDataURL('image/png');
        const pdf = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
        });

        const imgWidth = 210;
        const pageHeight = 297;
        const imgHeight = (canvas.height * imgWidth) / canvas.width;

        let heightLeft = imgHeight;
        let position = 0;

        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;

        // ✅ heightLeft가 정확히 0일 때 빈/중복 페이지가 생기는 문제 방지
        while (heightLeft > 0.5) {
          position = position - pageHeight; // 다음 페이지에서 이미지 위로 끌어올림
          pdf.addPage();
          pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
          heightLeft -= pageHeight;
        }

        pdf.save(fileName);
      } catch (err) {
        console.error('PDF Export failed:', err);
        alert('Failed to export PDF.');
      } finally {
        setIsExporting(false);
      }
    },
    [],
  );

  return { exportToPdf, isExporting };
}
