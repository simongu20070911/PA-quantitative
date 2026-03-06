import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";

import {
  buildInspectorRenderData,
  drawInspectorScene,
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

  constructor() {
    this.paneView = new InspectorPrimitivePaneView(this);
    this.paneViewsCache = [this.paneView];
  }

  attached(param: SeriesAttachedParameter<Time>) {
    this.attachedParam = param;
    this.rebuildRenderData();
  }

  detached() {
    this.attachedParam = null;
  }

  updateAllViews() {
    this.rebuildRenderData();
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.paneViewsCache;
  }

  setState(nextState: InspectorPrimitiveState) {
    this.state = nextState;
    this.rebuildRenderData();
    this.attachedParam?.requestUpdate();
  }

  renderer(): IPrimitivePaneRenderer | null {
    return new InspectorPrimitiveRenderer(this.renderData);
  }

  private rebuildRenderData() {
    if (!this.attachedParam) {
      return;
    }
    this.renderData = buildInspectorRenderData(this.state, {
      timeToCoordinate: (time) =>
        this.attachedParam?.chart.timeScale().timeToCoordinate(time as Time) ?? null,
      priceToCoordinate: (price) => this.attachedParam?.series.priceToCoordinate(price) ?? null,
    });
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

