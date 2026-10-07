/**
 * PDF export for benchmark / eval reports.
 *
 * Uses jsPDF + jspdf-autotable to produce a structured PDF from a BenchmarkReport.
 */

import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { BenchmarkReport } from '../models/benchmark.models';

export function exportReportPdf(report: BenchmarkReport | null): void {
  if (!report) return;

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  // --- Header ---
  doc.setFontSize(18);
  doc.text('Pachyderm Archive', pageWidth / 2, y, { align: 'center' });
  y += 8;
  doc.setFontSize(12);
  const mode = report.run_mode ?? 'pytest';
  doc.text(`${capitalize(mode)} Report`, pageWidth / 2, y, { align: 'center' });
  y += 8;
  doc.setFontSize(9);
  doc.setTextColor(100);
  doc.text(`Run ID: ${(report as any).run_id ?? 'N/A'}`, 14, y);
  doc.text(`Generated: ${report.generated_at ?? ''}`, pageWidth - 14, y, { align: 'right' });
  doc.setTextColor(0);
  y += 4;
  doc.text(`Model: ${(report as any).model_name ?? 'N/A'}  |  Suite: ${report.suite}`, 14, y);
  y += 8;

  // --- Summary Table ---
  const summary = report.summary;
  autoTable(doc, {
    startY: y,
    head: [['Metric', 'Value']],
    body: [
      ['Total Scenarios', String(summary.total)],
      ['Passed', String(summary.passed)],
      ['Failed', String(summary.failed)],
      ['Completion Rate', `${summary.completion_rate_percent?.toFixed(1) ?? 0}%`],
      ['Tool Precision', `${summary.tool_precision_percent?.toFixed(1) ?? 0}%`],
      ['Policy Compliance', `${summary.policy_compliance_percent?.toFixed(1) ?? 0}%`],
      ['Hallucinations', String(summary.hallucinations)],
    ],
    theme: 'striped',
    headStyles: { fillColor: [120, 113, 100] },
    margin: { left: 14, right: 14 },
  });
  y = (doc as any).lastAutoTable.finalY + 8;

  // --- Scenarios Table ---
  if (report.scenarios.length > 0) {
    doc.setFontSize(12);
    doc.text('Scenarios', 14, y);
    y += 4;

    autoTable(doc, {
      startY: y,
      head: [['Scenario', 'Status', 'Completion', 'Tool Precision', 'Hallucinations']],
      body: report.scenarios.map((s) => [
        s.scenario_id,
        s.status,
        `${((s.completion ?? 0) * 100).toFixed(0)}%`,
        s.tool_calls_total > 0
          ? `${((s.tool_calls_correct / s.tool_calls_total) * 100).toFixed(0)}%`
          : 'N/A',
        String(s.hallucinations),
      ]),
      theme: 'striped',
      headStyles: { fillColor: [120, 113, 100] },
      margin: { left: 14, right: 14 },
      styles: { fontSize: 8 },
    });
    y = (doc as any).lastAutoTable.finalY + 8;
  }

  // --- Benchmark Details ---
  if (report.benchmark_details) {
    const bd = report.benchmark_details;
    if (y > 250) {
      doc.addPage();
      y = 20;
    }

    doc.setFontSize(12);
    doc.text('Benchmark Details', 14, y);
    y += 4;

    autoTable(doc, {
      startY: y,
      head: [['Metric', 'Value']],
      body: [
        ['Interactions', String(bd.total_interactions)],
        ['Completed', String(bd.completed)],
        ['Errored', String(bd.errored)],
        ['Timed Out', String(bd.timed_out)],
        ['Avg Response Time', `${bd.avg_response_time_ms.toFixed(0)}ms`],
        ['Tool Engagement', `${bd.tool_engagement_rate.toFixed(1)}%`],
        ['Error Rate', `${bd.error_rate.toFixed(1)}%`],
        ['Wall Clock', `${bd.wall_clock_seconds.toFixed(1)}s`],
      ],
      theme: 'striped',
      headStyles: { fillColor: [120, 113, 100] },
      margin: { left: 14, right: 14 },
    });
    y = (doc as any).lastAutoTable.finalY + 8;

    // Domain breakdown
    const domains = Object.entries(bd.domain_breakdown);
    if (domains.length > 0) {
      autoTable(doc, {
        startY: y,
        head: [['Domain', 'Total', 'Completed', 'Errored']],
        body: domains.map(([domain, stats]) => [
          domain,
          String(stats.total),
          String(stats.completed),
          String(stats.errored),
        ]),
        theme: 'striped',
        headStyles: { fillColor: [120, 113, 100] },
        margin: { left: 14, right: 14 },
      });
      y = (doc as any).lastAutoTable.finalY + 8;
    }
  }

  // --- Forensic Assertions ---
  if (report.forensic_assertions.length > 0) {
    if (y > 250) {
      doc.addPage();
      y = 20;
    }

    doc.setFontSize(12);
    doc.text('Forensic Assertions', 14, y);
    y += 4;

    autoTable(doc, {
      startY: y,
      head: [['Assertion', 'Status', 'Evidence']],
      body: report.forensic_assertions.map((a) => [
        a.assertion_id,
        a.status,
        a.evidence.substring(0, 100),
      ]),
      theme: 'striped',
      headStyles: { fillColor: [120, 113, 100] },
      margin: { left: 14, right: 14 },
      styles: { fontSize: 8 },
    });
  }

  // --- Footer ---
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(150);
    doc.text(
      'Generated by Pachyderm Archive v2.5',
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 8,
      { align: 'center' },
    );
  }

  // Trigger download
  const runId = (report as any).run_id ?? 'report';
  doc.save(`benchmark-report-${runId}.pdf`);
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
