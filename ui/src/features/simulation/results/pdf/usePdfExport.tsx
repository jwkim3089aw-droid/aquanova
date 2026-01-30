// ui/src/features/flow-builder/ui/results/pdf/usePdfExport.tsx
import { useCallback, useState } from "react";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

export function usePdfExport() {
  const [isExporting, setIsExporting] = useState(false);

  const exportToPdf = useCallback(async (elementId: string, fileName: string = "report.pdf") => {
    const input = document.getElementById(elementId);
    if (!input) {
      console.error(`Element with id ${elementId} not found`);
      return;
    }

    try {
      setIsExporting(true);
      
      // 1. Capture: 2배율로 캡처하여 텍스트 선명도 확보
      const canvas = await html2canvas(input, {
        scale: 2, 
        useCORS: true, 
        logging: false,
        backgroundColor: "#ffffff" // 배경을 강제로 흰색으로 지정
      });

      // 2. PDF 생성
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4"
      });

      const imgWidth = 210; // A4 너비
      const pageHeight = 297; // A4 높이
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;

      // 첫 페이지
      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      // 내용이 길 경우 페이지 추가 (현재 1페이지로 딱 맞게 설계됨)
      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save(fileName);
    } catch (err) {
      console.error("PDF Export failed:", err);
      alert("Failed to export PDF.");
    } finally {
      setIsExporting(false);
    }
  }, []);

  return { exportToPdf, isExporting };
}