import type { AnalysisEvent } from '../../types/api';

export function parseAnalysisEvent(chunk: string): AnalysisEvent | null {
  const trimmed = chunk.trim();
  if (!trimmed) {
    return null;
  }

  const data = trimmed
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');

  if (!data) {
    return null;
  }

  try {
    const parsed = JSON.parse(data) as unknown;
    if (parsed && typeof parsed === 'object' && 'type' in parsed) {
      return parsed as AnalysisEvent;
    }
  } catch {
    return null;
  }

  return null;
}

export function shouldFinalizeAnalysisStream(event: AnalysisEvent): boolean {
  return event.type === 'task_finished';
}
