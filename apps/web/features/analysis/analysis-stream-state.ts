import type { AnalysisEvent, AnalysisReportTone } from '../../types/api';

export type StreamText = {
  stage1Reasoning: string;
  stage1Content: string;
  stage1BufferedContent: string;
  stage1ContentPending: boolean;
  stage1ContentComplete: boolean;
  stage2Reasoning: string;
  stage2Content: string;
  stage2BufferedContent: string;
  stage2ContentPending: boolean;
  stage2ContentComplete: boolean;
};

export const emptyStreamText: StreamText = {
  stage1Reasoning: '',
  stage1Content: '',
  stage1BufferedContent: '',
  stage1ContentPending: false,
  stage1ContentComplete: false,
  stage2Reasoning: '',
  stage2Content: '',
  stage2BufferedContent: '',
  stage2ContentPending: false,
  stage2ContentComplete: false,
};

type StageNumber = 1 | 2;

type StageState = {
  content: string;
  bufferedContent: string;
  contentPending: boolean;
  contentComplete: boolean;
};

type StreamPaneInput = StageState & {
  reasoning: string;
};

type StreamPaneDisplay = {
  body: string;
  tone: AnalysisReportTone;
};

function stageNumber(stage: string | undefined): StageNumber | null {
  if (stage === 'stage1') {
    return 1;
  }
  if (stage === 'stage2') {
    return 2;
  }
  return null;
}

function readString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function readStage(stream: StreamText, stage: StageNumber): StageState {
  if (stage === 1) {
    return {
      content: stream.stage1Content,
      bufferedContent: stream.stage1BufferedContent,
      contentPending: stream.stage1ContentPending,
      contentComplete: stream.stage1ContentComplete,
    };
  }
  return {
    content: stream.stage2Content,
    bufferedContent: stream.stage2BufferedContent,
    contentPending: stream.stage2ContentPending,
    contentComplete: stream.stage2ContentComplete,
  };
}

function writeStage(stream: StreamText, stage: StageNumber, state: StageState): StreamText {
  if (stage === 1) {
    return {
      ...stream,
      stage1Content: state.content,
      stage1BufferedContent: state.bufferedContent,
      stage1ContentPending: state.contentPending,
      stage1ContentComplete: state.contentComplete,
    };
  }
  return {
    ...stream,
    stage2Content: state.content,
    stage2BufferedContent: state.bufferedContent,
    stage2ContentPending: state.contentPending,
    stage2ContentComplete: state.contentComplete,
  };
}

export function appendAnalysisEventText(stream: StreamText, event: AnalysisEvent): StreamText {
  const text = readString(event.text);
  const stage = stageNumber(readString(event.stage));
  if (!stage) {
    return stream;
  }

  if (event.type === 'reasoning_delta' && text) {
    if (stage === 1) {
      return { ...stream, stage1Reasoning: stream.stage1Reasoning + text };
    }
    return { ...stream, stage2Reasoning: stream.stage2Reasoning + text };
  }

  if (event.type === 'content_started') {
    return writeStage(stream, stage, {
      content: '',
      bufferedContent: '',
      contentPending: true,
      contentComplete: false,
    });
  }

  if (event.type === 'content_delta' && text) {
    const current = readStage(stream, stage);
    if (current.contentPending || current.bufferedContent) {
      return writeStage(stream, stage, {
        ...current,
        bufferedContent: current.bufferedContent + text,
      });
    }
    return writeStage(stream, stage, {
      ...current,
      content: current.content + text,
    });
  }

  if (event.type === 'content_finished') {
    const current = readStage(stream, stage);
    const fullText = text || current.bufferedContent;
    return writeStage(stream, stage, {
      content: fullText,
      bufferedContent: fullText,
      contentPending: false,
      contentComplete: true,
    });
  }

  return stream;
}

export function streamPaneDisplay(input: StreamPaneInput): StreamPaneDisplay {
  const sections: string[] = [];
  if (input.reasoning) {
    let text = input.reasoning;
    
    // Hide markdown JSON blocks from the reasoning stream to avoid exposing raw data
    text = text.replace(/```(?:json)?[\s\S]*?(?:```|$)/gi, '\n[JSON data hidden]');
    
    // Hide common meta-reasoning about JSON formatting that leaks data points
    const markerIndex = text.search(/现在开始组织JSON|现在构建JSON|我要输出一个完整的JSON/);
    if (markerIndex !== -1) {
      text = text.slice(0, markerIndex) + '\n[JSON construction hidden]';
    }

    sections.push(`[reasoning]\n${text.trim()}`);
  }
  if (input.contentPending) {
    sections.push('[content]\nWaiting for structured JSON completion marker.');
    return {
      body: sections.join('\n\n'),
      tone: 'warn',
    };
  }
  if (input.contentComplete) {
    sections.push('[content]\nStructured JSON received. Analysis report is rendered below.');
    return {
      body: sections.join('\n\n'),
      tone: 'good',
    };
  }
  if (input.content) {
    sections.push(`[content]\n${input.content}`);
  }
  return {
    body: sections.join('\n\n') || 'Waiting for stream output.',
    tone: input.content || input.reasoning ? 'good' : 'neutral',
  };
}
