from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from pa_core.data.bar_families import BarFamilyUnsupportedError

from .models import (
    ChartWindowResponse,
    OverlayLayer,
    SessionProfile,
    StructureDetailResponse,
)
from .service import (
    ChartApiConfig,
    ChartApiService,
    ChartWindowSelectionError,
    StructureNotFoundError,
)


def create_app(service: ChartApiService | None = None) -> FastAPI:
    app = FastAPI(title="PA Quantitative API", version="0.1.0")
    chart_service = service or ChartApiService()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/chart-window", response_model=ChartWindowResponse)
    def get_chart_window(
        symbol: str = Query(...),
        timeframe: str = Query(...),
        session_profile: SessionProfile = Query(default="eth_full"),
        center_bar_id: int | None = Query(default=None),
        session_date: int | None = Query(default=None),
        start_time: int | None = Query(default=None),
        end_time: int | None = Query(default=None),
        left_bars: int = Query(default=300, ge=0),
        right_bars: int = Query(default=300, ge=0),
        buffer_bars: int = Query(default=100, ge=0),
        overlay_layer: list[OverlayLayer] | None = Query(default=None),
        data_version: str | None = Query(default=None),
        feature_version: str | None = Query(default=None),
        feature_params_hash: str | None = Query(default=None),
        overlay_version: str | None = Query(default=None),
        ema_length: list[int] | None = Query(default=None),
    ) -> ChartWindowResponse:
        try:
            return chart_service.get_chart_window(
                symbol=symbol,
                timeframe=timeframe,
                session_profile=session_profile,
                center_bar_id=center_bar_id,
                session_date=session_date,
                start_time=start_time,
                end_time=end_time,
                left_bars=left_bars,
                right_bars=right_bars,
                buffer_bars=buffer_bars,
                overlay_layers=overlay_layer,
                data_version=data_version,
                feature_version=feature_version,
                feature_params_hash=feature_params_hash,
                overlay_version=overlay_version,
                ema_lengths=ema_length,
            )
        except ChartWindowSelectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BarFamilyUnsupportedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/structure/{structure_id}", response_model=StructureDetailResponse)
    def get_structure_detail(
        structure_id: str,
        symbol: str = Query(...),
        timeframe: str = Query(...),
        session_profile: SessionProfile = Query(default="eth_full"),
        data_version: str | None = Query(default=None),
        feature_version: str | None = Query(default=None),
        feature_params_hash: str | None = Query(default=None),
        overlay_version: str | None = Query(default=None),
    ) -> StructureDetailResponse:
        try:
            return chart_service.get_structure_detail(
                structure_id=structure_id,
                symbol=symbol,
                timeframe=timeframe,
                session_profile=session_profile,
                data_version=data_version,
                feature_version=feature_version,
                feature_params_hash=feature_params_hash,
                overlay_version=overlay_version,
            )
        except ChartWindowSelectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except BarFamilyUnsupportedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except StructureNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown structure_id: {exc.args[0]}") from exc

    return app


app = create_app()
