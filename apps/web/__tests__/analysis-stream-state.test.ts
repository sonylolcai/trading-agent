import { describe, expect, it } from 'vitest';
import {
  appendAnalysisEventText,
  emptyStreamText,
  streamPaneDisplay,
} from '../features/analysis/analysis-stream-state';

describe('appendAnalysisEventText', () => {
  it('buffers structured stage content until the completion marker arrives', () => {
    let stream = emptyStreamText;

    stream = appendAnalysisEventText(stream, { type: 'content_started', stage: 'stage1', format: 'json' });
    stream = appendAnalysisEventText(stream, { type: 'content_delta', stage: 'stage1', text: '{"cycle":' });
    stream = appendAnalysisEventText(stream, { type: 'content_delta', stage: 'stage1', text: '"up"}' });

    expect(stream.stage1Content).toBe('');
    expect(stream.stage1BufferedContent).toBe('{"cycle":"up"}');
    expect(stream.stage1ContentPending).toBe(true);

    stream = appendAnalysisEventText(stream, { type: 'content_finished', stage: 'stage1', format: 'json' });

    expect(stream.stage1Content).toBe('{"cycle":"up"}');
    expect(stream.stage1ContentPending).toBe(false);
    expect(stream.stage1ContentComplete).toBe(true);
  });

  it('keeps legacy content deltas visible when no structured header is present', () => {
    const stream = appendAnalysisEventText(emptyStreamText, { type: 'content_delta', stage: 'stage2', text: 'plain text' });

    expect(stream.stage2Content).toBe('plain text');
    expect(stream.stage2BufferedContent).toBe('');
    expect(stream.stage2ContentPending).toBe(false);
  });
});

describe('streamPaneDisplay', () => {
  it('does not expose raw json while a structured stage is still streaming', () => {
    const display = streamPaneDisplay({
      reasoning: '',
      content: '',
      bufferedContent: '{"cycle":"up"}',
      contentPending: true,
      contentComplete: false,
    });

    expect(display.body).toContain('Waiting for structured JSON completion marker.');
    expect(display.body).not.toContain('{"cycle":"up"}');
    expect(display.tone).toBe('warn');
  });

  it('replaces completed structured json with a rendering status message', () => {
    const display = streamPaneDisplay({
      reasoning: 'checking context',
      content: '{"cycle":"up"}',
      bufferedContent: '{"cycle":"up"}',
      contentPending: false,
      contentComplete: true,
    });

    expect(display.body).toContain('[reasoning]\nchecking context');
    expect(display.body).toContain('Structured JSON received. Analysis report is rendered below.');
    expect(display.body).not.toContain('{"cycle":"up"}');
    expect(display.tone).toBe('good');
  });
});
