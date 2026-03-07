import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";

import {
  buildBarTimeIndex,
  buildInspectorGeometryCache,
  buildInspectorPresentationState,
  buildInspectorRenderData,
  composeInspectorRenderData,
  drawInspectorScene,
  type InspectorGeometryCache,
  type InspectorRenderData,
  type InspectorPresentationState,
  type InspectorPrimitiveState,
} from "./inspectorScene";

export class InspectorPrimitive implements ISeriesPrimitive<Time> {
  private attachedParam: SeriesAttachedParameter<Time> | null = null;
  private readonly paneViewsCache: readonly IPrimitivePaneView[];
  private readonly paneView: InspectorPrimitivePaneView;
  private state: InspectorPrimitiveState = {
    bars: [],
    overlays: [],
    annotations: [],
    selectedOverlayId: null,
    selectedAnnotationId: null,
    confirmationGuide: null,
    sessionProfile: "eth_full",
    draftAnnotation: null,
  };
  private renderData = buildInspectorRenderData(this.state, {
    timeToCoordinate: () => null,
    priceToCoordinate: () => null,
  });
  private geometryCache: InspectorGeometryCache = {
    barTimeById: new Map(),
    sessionBoundaries: [],
    overlayDrawables: [],
    annotationDrawables: [],
  };
  private presentationState: InspectorPresentationState = {
    confirmationGuide: null,
    draftDrawable: null,
    selectedOverlayId: null,
    selectedAnnotationId: null,
  };
  private refreshRafId: number | null = null;
  private dirtyAllProjected = true;
  private dirtyBarIndex = true;
  private dirtyOverlayGeometry = true;
  private dirtyAnnotationGeometry = true;
  private dirtySessionBoundaries = true;
  private dirtyPresentation = true;

  constructor() {
    this.paneView = new InspectorPrimitivePaneView(this);
    this.paneViewsCache = [this.paneView];
  }

  attached(param: SeriesAttachedParameter<Time>) {
    this.attachedParam = param;
    this.markAllDirty();
    this.flushRefresh();
  }

  detached() {
    if (this.refreshRafId !== null) {
      window.cancelAnimationFrame(this.refreshRafId);
      this.refreshRafId = null;
    }
    this.attachedParam = null;
  }

  updateAllViews() {
    this.markAllDirty();
    this.flushRefresh();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.paneViewsCache;
  }

  setState(nextState: InspectorPrimitiveState) {
    const previousState = this.state;
    this.state = nextState;
    const barsChanged = previousState.bars !== nextState.bars;
    const overlaysChanged = previousState.overlays !== nextState.overlays;
    const annotationsChanged = previousState.annotations !== nextState.annotations;
    const sessionProfileChanged =
      previousState.sessionProfile !== nextState.sessionProfile;
    const presentationChanged =
      previousState.confirmationGuide !== nextState.confirmationGuide ||
      previousState.draftAnnotation !== nextState.draftAnnotation ||
      previousState.selectedOverlayId !== nextState.selectedOverlayId ||
      previousState.selectedAnnotationId !== nextState.selectedAnnotationId;

    if (barsChanged) {
      this.dirtyBarIndex = true;
      this.dirtyOverlayGeometry = true;
      this.dirtyAnnotationGeometry = true;
      this.dirtySessionBoundaries = true;
      this.dirtyPresentation = true;
    } else {
      if (overlaysChanged) {
        this.dirtyOverlayGeometry = true;
      }
      if (annotationsChanged) {
        this.dirtyAnnotationGeometry = true;
      }
      if (sessionProfileChanged) {
        this.dirtySessionBoundaries = true;
      }
      if (presentationChanged) {
        this.dirtyPresentation = true;
      }
    }
    this.refresh();
  }

  refresh() {
    this.dirtyAllProjected = true;
    this.scheduleRefresh();
  }

  getRenderData(): InspectorRenderData {
    return this.renderData;
  }

  renderer(): IPrimitivePaneRenderer | null {
    return new InspectorPrimitiveRenderer(this.renderData);
  }

  private markAllDirty() {
    this.dirtyAllProjected = true;
    this.dirtyBarIndex = true;
    this.dirtyOverlayGeometry = true;
    this.dirtyAnnotationGeometry = true;
    this.dirtySessionBoundaries = true;
    this.dirtyPresentation = true;
  }

  private scheduleRefresh() {
    if (this.refreshRafId !== null) {
      return;
    }
    this.refreshRafId = window.requestAnimationFrame(() => {
      this.refreshRafId = null;
      this.flushRefresh();
    });
  }

  private flushRefresh() {
    if (!this.attachedParam) {
      return;
    }
    const projector = {
      timeToCoordinate: (time: number) =>
        this.attachedParam?.chart.timeScale().timeToCoordinate(time as Time) ?? null,
      priceToCoordinate: (price: number) =>
        this.attachedParam?.series.priceToCoordinate(price) ?? null,
    };

    if (this.dirtyBarIndex) {
      this.geometryCache.barTimeById = buildBarTimeIndex(this.state.bars);
      this.dirtyBarIndex = false;
    }

    if (this.dirtyAllProjected || this.dirtyOverlayGeometry) {
      this.geometryCache.overlayDrawables = buildInspectorGeometryCache(
        {
          bars: this.state.bars,
          overlays: this.state.overlays,
          annotations: [],
          sessionProfile: "eth_full",
        },
        projector,
        this.geometryCache.barTimeById,
      ).overlayDrawables;
      this.dirtyOverlayGeometry = false;
    }

    if (this.dirtyAllProjected || this.dirtyAnnotationGeometry) {
      this.geometryCache.annotationDrawables = buildInspectorGeometryCache(
        {
          bars: this.state.bars,
          overlays: [],
          annotations: this.state.annotations,
          sessionProfile: "eth_full",
        },
        projector,
        this.geometryCache.barTimeById,
      ).annotationDrawables;
      this.dirtyAnnotationGeometry = false;
    }

    if (this.dirtyAllProjected || this.dirtySessionBoundaries) {
      this.geometryCache.sessionBoundaries = buildInspectorGeometryCache(
        {
          bars: this.state.bars,
          overlays: [],
          annotations: [],
          sessionProfile: this.state.sessionProfile,
        },
        projector,
        this.geometryCache.barTimeById,
      ).sessionBoundaries;
      this.dirtySessionBoundaries = false;
    }

    if (this.dirtyAllProjected || this.dirtyPresentation) {
      this.presentationState = buildInspectorPresentationState(
        this.state,
        this.geometryCache.barTimeById,
        projector,
      );
      this.dirtyPresentation = false;
    }

    this.dirtyAllProjected = false;
    this.renderData = composeInspectorRenderData(
      this.geometryCache,
      this.presentationState,
    );
    this.attachedParam.requestUpdate();
  }
}

class InspectorPrimitivePaneView implements IPrimitivePaneView {
  constructor(private readonly primitive: InspectorPrimitive) {}

  zOrder() {
    return "top" as const;
  }

  renderer(): IPrimitivePaneRenderer | null {
    return this.primitive.renderer();
  }
}

class InspectorPrimitiveRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly data: ReturnType<typeof buildInspectorRenderData>) {}

  draw(target: Parameters<IPrimitivePaneRenderer["draw"]>[0]) {
    drawInspectorScene(target, this.data);
  }
}
