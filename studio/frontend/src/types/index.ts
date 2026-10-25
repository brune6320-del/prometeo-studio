/**
 * PROMETEO Studio · tipos compartidos con el backend (contrato API 2.1).
 */

export interface HealthInfo {
  status: 'ok' | 'degraded';
  ready: boolean;
  version: string;
  api_version: string;
  runtime_mode: string;
  workspace: { ok: boolean; source: string | null; error_code: string | null };
  ocr_available: boolean;
}

/** Estado del arranque informado por el host nativo (nunca contiene el token). */
export interface HostStatus {
  state: 'STARTING' | 'BACKEND_READY' | 'DEGRADED' | 'FAILED';
  port: number;
  code: string | null;
  message: string | null;
  exit_code: number | null;
  log_path: string | null;
  workspace_path: string | null;
  elapsed_ms: number;
}

export interface SavedCopy {
  ok: boolean;
  path: string;
  filename: string;
  folder: string;
  sha256: string;
  original_unchanged: boolean;
}

export type ResultState =
  | 'OPENED'
  | 'READY'
  | 'STAGED'
  | 'VERIFIED'
  | 'AMBIGUOUS'
  | 'HONEST_REJECT'
  | 'FAILED'
  | 'CRASH'
  | 'SILENT_FAILURE';

export type NodeType = 'DOCUMENT' | 'PAGE' | 'GROUP' | 'TEXT' | 'VECTOR' | 'IMAGE';

export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface NodeSummary {
  id: string;
  type: NodeType;
  page?: number;
  bbox?: [number, number, number, number];
  text?: string;
  font?: string;
  size?: number;
  children_count?: number;
  children?: NodeSummary[];
  parent_id?: string;
}

export interface RelationSummary {
  rel_type: string;
  target_id: string;
  origin: 'MATERIALIZED' | 'DERIVED';
}

export interface NodeDetail {
  id: string;
  type: NodeType;
  page?: number;
  bbox?: [number, number, number, number];
  text?: string;
  font?: string;
  size?: number;
  origin?: [number, number];
  clearance_pt?: number;
  parent_id?: string;
  children_ids?: string[];
  relations?: RelationSummary[];
  properties?: Record<string, any>;
}

export interface PageRenderData {
  page_number: number;
  width_pt: number;
  height_pt: number;
  pixel_width: number;
  pixel_height: number;
  dpi: number;
  scale_x: number;
  scale_y: number;
  rotation: number;
  image_data_url: string;
}

export interface DocumentSummary {
  filename?: string;
  document_id: string;
  source_sha256: string;
  pages_count: number;
  total_nodes: number;
  text_nodes_count: number;
  image_nodes_count: number;
  vector_nodes_count: number;
  docgraph_version: string;
  session_id: string;
  transaction_state: string;
  staged_count: number;
  capabilities: {
    is_born_digital: boolean;
    is_raster?: boolean;
    is_raster_dominant?: boolean;
    can_text_edit?: boolean;
    can_verify_physically?: boolean;
    has_ocr_layer?: boolean;
    capability_badge: string;
    warning?: string;
  };
}

export interface OutlineItem {
  id: string;
  title: string;
  type: NodeType;
  page: number;
  bbox?: [number, number, number, number];
  children?: OutlineItem[];
}

export interface SearchCandidate {
  candidate_id: string;
  page: number;
  span_id: string;
  text: string;
  matched_query: string;
  bbox: [number, number, number, number];
  origin: [number, number];
  font: string;
  size: number;
  clearance_pt: number;
  node_id: string;
}

export interface SearchResult {
  ok: boolean;
  status: string;
  result_state: string;
  query: string;
  count: number;
  candidates?: SearchCandidate[];
  candidate_id?: string;
  node_id?: string;
  is_ambiguous?: boolean;
  message?: string;
}

export interface StagedOperation {
  op_id: string;
  type?: 'VECTOR_REPLACE_TEXT' | 'RASTER_REPLACE_TEXT';
  node_id: string;
  target_id?: string;
  original_text: string;
  new_text: string;
  page?: number;
  status: string;
  timestamp?: string;
}

export interface TransactionTrayData {
  ok: boolean;
  transaction_state: string;
  staged_operations: StagedOperation[];
  count: number;
}

export interface VerifierOpDetail {
  op_id: string;
  target_id: string;
  expected_text: string;
  found_text: string;
  text_ok: boolean;
  dx_ok: boolean;
  dy_ok: boolean;
  font_ok: boolean;
  pass: boolean;
}

export interface VerifierResult {
  ok?: boolean;
  verdict: 'PASS' | 'FAILED' | 'HONEST_REJECT';
  status: string;
  code?: string | null;
  transaction_id?: string | null;
  operations_verified?: number;
  verifier_executed?: boolean;
  verifier_profile?: string | null;
  details?: Array<Record<string, any>>;
  verified_globally: boolean;
  reason?: string;
}

export interface ChangedNodeDiff {
  node_id: string;
  page: number;
  text_before: string;
  text_after: string;
  font_before?: string;
  font_after?: string;
  bbox_before?: [number, number, number, number];
  bbox_after?: [number, number, number, number];
  bbox_delta?: {
    dx0: number;
    dy0: number;
    dx1: number;
    dy1: number;
    d_width: number;
    d_height: number;
  };
}

export interface DocGraphDiffResult {
  is_identical: boolean;
  source_sha256_before: string;
  source_sha256_after: string;
  summary: {
    added_count: number;
    removed_count: number;
    changed_count: number;
    total_nodes_before: number;
    total_nodes_after: number;
  };
  added_nodes: any[];
  removed_nodes: any[];
  changed_nodes: ChangedNodeDiff[];
}

export interface VerifyAndExportResponse {
  ok: boolean;
  transaction_state: string;
  verifier_result: VerifierResult;
  published: boolean;
  diff?: DocGraphDiffResult;
  output_filename?: string;
  output_sha256?: string;
  original_unchanged?: boolean;
  original_sha256?: string;
  error?: string;
  error_code?: string;
}

export interface AgentProposedOp {
  node_id: string;
  target_id?: string;
  original_text: string;
  new_text: string;
  page?: number;
}

export interface AgentChatMessage {
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  proposed_transaction?: {
    intent: string;
    operations: AgentProposedOp[];
  };
  tool_trace?: string[];
  candidates?: SearchCandidate[];
}

export interface SampleItem {
  key: string;
  filename: string;
  description: string;
  pages?: number;
}

export interface OCRObservation {
  id: string;
  observation_id: string;
  page: number;
  text: string;
  bbox: [number, number, number, number];
  confidence: number;
  engine: string;
  config: string;
  provenance: string;
  is_native_entity: boolean;
  capability_state: string;
  editing_state: string;
}

export interface OCRLayerData {
  error_code?: string;
  error?: string;
  ok: boolean;
  page: number;
  observations_count: number;
  observations: OCRObservation[];
  status: string;
  editing_status: string;
  epistemic_disclaimer: string;
}

export interface RasterSafetyData {
  ok: boolean;
  observation_id: string;
  page: number;
  raster_class: string;
  safety_classification: string;
  edit_eligible: boolean;
  reasons: string[];
  metrics: Record<string, any>;
  thresholds: Record<string, any>;
  allowed_patch_bbox_pt: [number, number, number, number];
  profile_name: string;
}

export interface RasterPatchPreviewData {
  ok: boolean;
  edit_eligible: boolean;
  raster_class: string;
  safety_classification?: string;
  before_data_url: string;
  preview_data_url: string;
  allowed_patch_bbox_pt?: [number, number, number, number];
  target_bbox_pt?: [number, number, number, number];
  metrics?: Record<string, any>;
  reasons?: string[];
  ring_delta_estimate?: number;
}

export interface MirarReferenteInput {
  id: string;
  nombre: string;
  por_que: string;
  archivo_origen: string;
  etiquetas: string[];
  url: string;
}

export interface MirarReferentesRequest {
  proyecto: string;
  ojos: string;
  ojos_descripcion: string;
  preguntas: string[];
  referentes: MirarReferenteInput[];
}

export interface MirarReferenteLectura {
  texto?: string;
  modelo?: string;
}

export interface MirarReferentesResponse {
  ok: boolean;
  disponible?: boolean;
  motivo?: string | null;
  modelo?: string;
  lecturas?: MirarReferenteLectura[];
}

export interface ManifiestoRequest {
  proyecto: string;
  collages: string[];
  lecturas: string[];
  pesos: string[];
}

export interface ManifiestoResponse {
  ok: boolean;
  disponible?: boolean;
  motivo?: string | null;
  modelo?: string;
  lineas?: string[];
}

/** H8 · salida de una herramienta de documento: siempre un PDF nuevo con SHA-256. */
export interface AdvancedOutput {
  ok: boolean;
  code?: string;
  reason?: string;
  filename?: string;
  token?: string;
  sha256?: string;
  download_url?: string;
  others_unchanged?: boolean;
  target_span?: {
    page: number;
    bbox: number[];
    old_text: string;
    new_text: string;
    font: string;
    size_pt: number;
    color: string;
  };
  measured_width_pt?: number;
  available_width_pt?: number;
  suggested_size_pt?: number;
  layer?: string;
  page?: number;
  kind?: string;
  pages?: number;
}
