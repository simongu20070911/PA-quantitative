import type {
  ChartWindowRequest,
  ChartWindowResponse,
  StructureDetailResponse,
} from "./types";

const CHART_WINDOW_TIMEOUT_MS = 0;
const STRUCTURE_DETAIL_TIMEOUT_MS = 10_000;

function buildBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.endsWith("/") ? apiBaseUrl.slice(0, -1) : apiBaseUrl;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // fall through to the default message
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

async function fetchJsonWithTimeout<T>(
  url: string,
  timeoutMs: number,
): Promise<T> {
  if (timeoutMs <= 0) {
    const response = await fetch(url);
    return readJson<T>(response);
  }

  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(url, {
      signal: controller.signal,
    });
    return readJson<T>(response);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.floor(timeoutMs / 1000)}s.`);
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export async function fetchChartWindow(
  request: ChartWindowRequest,
): Promise<ChartWindowResponse> {
  const params = new URLSearchParams({
    symbol: request.symbol,
    timeframe: request.timeframe,
    session_profile: request.sessionProfile,
    data_version: request.dataVersion,
    structure_source: request.structureSource,
    left_bars: String(request.leftBars),
    right_bars: String(request.rightBars),
    buffer_bars: String(request.bufferBars),
  });

  if (request.featureVersion) {
    params.set("feature_version", request.featureVersion);
  }
  if (request.featureParamsHash) {
    params.set("feature_params_hash", request.featureParamsHash);
  }
  if (request.overlayVersion) {
    params.set("overlay_version", request.overlayVersion);
  }
  if (request.asOfBarId !== null && request.asOfBarId !== undefined) {
    params.set("as_of_bar_id", String(request.asOfBarId));
  }
  for (const length of request.emaLengths ?? []) {
    params.append("ema_length", String(length));
  }

  if (request.selectorMode === "center_bar_id" && request.centerBarId) {
    params.set("center_bar_id", request.centerBarId);
  } else if (request.selectorMode === "session_date" && request.sessionDate) {
    params.set("session_date", request.sessionDate);
  } else if (
    request.selectorMode === "time_range" &&
    request.startTime &&
    request.endTime
  ) {
    params.set("start_time", request.startTime);
    params.set("end_time", request.endTime);
  }

  for (const layer of request.overlayLayers ?? []) {
    params.append("overlay_layer", layer);
  }

  return fetchJsonWithTimeout<ChartWindowResponse>(
    `${buildBaseUrl(request.apiBaseUrl)}/chart-window?${params.toString()}`,
    CHART_WINDOW_TIMEOUT_MS,
  );
}

export async function fetchStructureDetail(args: {
  apiBaseUrl: string;
  structureId: string;
  symbol: string;
  timeframe: string;
  sessionProfile: string;
  dataVersion: string;
  structureSource: string;
  asOfBarId?: number | null;
}): Promise<StructureDetailResponse> {
  const params = new URLSearchParams({
    symbol: args.symbol,
    timeframe: args.timeframe,
    session_profile: args.sessionProfile,
    data_version: args.dataVersion,
    structure_source: args.structureSource,
  });
  if (args.asOfBarId !== null && args.asOfBarId !== undefined) {
    params.set("as_of_bar_id", String(args.asOfBarId));
  }
  return fetchJsonWithTimeout<StructureDetailResponse>(
    `${buildBaseUrl(args.apiBaseUrl)}/structure/${args.structureId}?${params.toString()}`,
    STRUCTURE_DETAIL_TIMEOUT_MS,
  );
}
