import type {
  ChartWindowRequest,
  ChartWindowResponse,
  StructureDetailResponse,
} from "./types";

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

export async function fetchChartWindow(
  request: ChartWindowRequest,
): Promise<ChartWindowResponse> {
  const params = new URLSearchParams({
    symbol: request.symbol,
    timeframe: request.timeframe,
    session_profile: request.sessionProfile,
    data_version: request.dataVersion,
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

  const response = await fetch(
    `${buildBaseUrl(request.apiBaseUrl)}/chart-window?${params.toString()}`,
  );
  return readJson<ChartWindowResponse>(response);
}

export async function fetchStructureDetail(args: {
  apiBaseUrl: string;
  structureId: string;
  symbol: string;
  timeframe: string;
  sessionProfile: string;
  dataVersion: string;
}): Promise<StructureDetailResponse> {
  const params = new URLSearchParams({
    symbol: args.symbol,
    timeframe: args.timeframe,
    session_profile: args.sessionProfile,
    data_version: args.dataVersion,
  });
  const response = await fetch(
    `${buildBaseUrl(args.apiBaseUrl)}/structure/${args.structureId}?${params.toString()}`,
  );
  return readJson<StructureDetailResponse>(response);
}
