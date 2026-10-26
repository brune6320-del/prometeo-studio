import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  Archive,
  ChevronDown,
  FolderPlus,
  History,
  Hand,
  Magnet,
  Download,
  LayoutTemplate,
  Library,
  Link2,
  List,
  Lock,
  LockOpen,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  Undo2,
  Upload,
  Redo2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import {
  boardFilename,
  boardToMarkdown,
  cloneBoardForImport,
  createBoard,
  createCard,
  createMediaCard,
  DEFAULT_BOARD_SETTINGS,
  duplicateCards,
  isSafeExternalUrl,
  makeBoardExport,
  markdownToBoard,
  MAX_MEDIA_BYTES,
  newBoardId,
  normalizeBoard,
  parseBoardImport,
  type BoardCard,
  type BoardDocument,
  type BoardMedia,
  type BoardRelation,
  type BoardSettings,
} from '../board/model';
import { geometriaConector, rectDeTarjeta } from '../board/conectores';
import { vecinoGeometrico, type Direccion } from '../board/navegacion';
import { coincideBusqueda, ordenDePintado, ventanaVirtual, INDICE_ROW_HEIGHT } from '../board/indice';
import { readColumnData, normalizeColumnData, setColumnFolded, columnChildIds, COLUMN_MIN_HEIGHT, quitarHijoDeColumna, reordenarHijoDeColumna } from '../board/columnas';
import { normalizarVistaPrevia } from '../board/vistaPrevia';
import { borrarPlantillasLegacy, crearPlantilla, leerPlantillasLegacy, listarPlantillas, materializar, type Plantilla } from '../board/plantillas';
import { ABRIR_TABLERO_EVENT } from '../board/tools/tablero';
import { studioApi } from '../api/client';
import { factorDePellizco, fitBoardCamera, zoomAtPoint, screenToWorld } from '../board/camera';
import { movimientoReducido, pasoInercia, velocidadDeMuestras, type MuestraInercia } from '../motion/muelle';
import { alignCards, distributeCards, snapPosition, type Alignment, type CardSize, type DistributionAxis } from '../board/geometry';
import { imanDeCaja, inclinacionPorVelocidad, type GuiasIman } from '../board/iman';
import { esMediaLibre, medirMedio } from '../board/medio';
import {
  cardsInsideFrame,
  FRAME_MIN_SIZE,
  normalizeFrameData,
  readFrameData,
  rectFromPoints,
  setFrameView,
  type FrameRect,
  type FrameView,
} from '../board/frames';
import { emptyBoardHistory, recordBoardChange, redoBoardChange, undoBoardChange, type BoardHistory } from '../board/history';
import {
  atajoParaEvento,
  esObjetivoDeTexto,
  gruposDeAyuda,
  textoAtajo,
  type AtajoLienzo,
} from '../board/atajos';
import {
  alternarEnSeleccion,
  aplicarMarquesina,
  borrarTarjetas,
  claveDeRafaga,
  duplicarSeleccion,
  moverTarjetas,
  reordenarTarjetas,
  seleccionarTodoElTablero,
  tarjetasAMover,
} from '../board/seleccion';
import {
  copiarTarjetas,
  esMarcaDeTarjetas,
  hayTarjetasCopiadas,
  pegarTarjetasEn,
  textoLegibleDeTarjetas,
} from '../board/portapapeles';
import { agregarImagenDesdeUrl, importarBiblioteca } from '../board/referentes/biblioteca';
import { construirZipObsidian, notasObsidian } from '../board/referentes/historial';
import { aceptarLectura } from '../board/referentes/mirar';
import { leerReferente, type Lectura } from '../board/referentes/model';
import { loadBoardWorkspace } from '../board/storage';
import { guardarHistorial, leerHistoriales, listarBorrados, olvidarBorrado, recordarBorrado, tomarBorrado, type BorradoEntry, type BorradoKind } from '../board/memoria';
import { BoardToolMenu } from '../board/tools/menu';
import { DESIGN_SYSTEMS, normalizeDesignSystem, type DesignSystemId } from '../board/diseno';
import { getBoardTool, listBoardTools } from '../board/tools/registry';
import { EntropiaVista } from '../board/tools/entropiaVista';
import {
  esMarcoEntropia,
  leerEntropia,
  nuevaSemilla,
  tirarEntropia,
  type EntropiaDatos,
  type FuenteEntropia,
} from '../board/vanguardia/entropia';
import { gustosVacios, importarGustosParciales, like, nope, type Gustos } from '../board/vanguardia/gustos';
import { crearMarcoManifiesto, pedirManifiesto, seleccionarSemana } from '../board/vanguardia/manifiesto';
import { enqueueBoardSave, flushBoardWrites, removeBoardFromStore, rememberActiveBoard } from '../board/saveQueue';
import { marca, marcaFin } from '../board/marcas';
import { publishFrameToDirectory } from '../board/publicar';
import {
  createPdfReference,
  projectToMarkdown,
  type BoardProject,
  type PdfReference,
  type PdfReferenceSource,
} from '../board/projectModel';
import {
  addProjectPlantillas,
  assignBoardToProject,
  createProject,
  deletePdfReference,
  deleteProjectPlantilla,
  loadProjectWorkspace,
  removeBoardProjectLink,
  removeProjectRecord,
  renameProject,
  saveProjectRecord,
  savePdfReference,
  saveProjectGustos,
  saveProjectPlantilla,
  setActiveProject,
  setProjectArchived,
} from '../board/projectStorage';
import { useBoardWrites } from '../hooks/useBoardWrites';
import { BoardCardItem } from './BoardCardItem';
import { BoardColumn } from './BoardColumn';
import { BoardFreeMedia, leerRecorte, type EsquinaMedia } from './BoardFreeMedia';
import { TituloEnSitio } from './InlineEdit';
import { useFocusTrap } from './useFocusTrap';
import { MirarDialog } from './MirarDialog';
import { ArchivoView } from './ArchivoView';
import { MuroView } from './MuroView';
import { MesaView } from './MesaView';
import './board.css';

interface BoardWorkspaceProps {
  onBack: () => void;
  /** Con un diálogo de cierre abierto el tablero no recibe interacción. */
  locked?: boolean;
  engineMessage?: string;
  onRetryEngine?: () => void;
  pdfReferenceSource?: PdfReferenceSource | null;
  onOpenPdfReference?: (reference: PdfReference) => boolean;
}

const GRID_SIZE = 24;
const COLORS: Array<BoardCard['color']> = ['paper', 'sand', 'sage', 'rose'];
const RAIL_TOOLS = ['note', 'link', 'media', 'tareas', 'columna', 'referente', 'marco', 'entropia'];
const DIRECCIONES_ASA = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'];
const ETIQUETA_BORRADO: Record<BorradoKind, string> = {
  board: 'Tablero',
  reference: 'Referencia PDF',
  cards: 'Tarjetas',
  project: 'Proyecto',
};

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => (typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('No se pudo leer el archivo.')));
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

function liberarPuntero(element: HTMLElement | null, pointerId: number): void {
  if (!element) return;
  try {
    if (element.hasPointerCapture(pointerId)) element.releasePointerCapture(pointerId);
  } catch {
    /* el elemento ya no existe o el puntero se soltó solo */
  }
}

/** Normaliza deltaMode (píxel, línea o página) a píxeles de pantalla. */
function deltaDeRueda(event: WheelEvent, altoViewport: number): { x: number; y: number } {
  const escala = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? altoViewport : 1;
  return { x: event.deltaX * escala, y: event.deltaY * escala };
}

function downloadText(filename: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

interface Modificadores {
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
}

interface GestoWebKit extends Event {
  scale?: number;
  clientX?: number;
  clientY?: number;
}

interface CardHandlers {
  select: (cardId: string, event: Modificadores) => void;
  connect: (cardId: string) => void;
  connectStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>) => void;
  dragStart: (card: BoardCard, event: React.PointerEvent<HTMLElement>, force?: boolean) => void;
  dragMove: (event: React.PointerEvent<HTMLElement>) => void;
  dragEnd: (event: React.PointerEvent<HTMLElement>) => void;
  delete: (cardId: string) => void;
  patch: (cardId: string, patch: Partial<BoardCard>) => void;
  replace: (card: BoardCard) => void;
  hover: (cardId: string, over: boolean) => void;
  blur: () => void;
}

export const BoardWorkspace: React.FC<BoardWorkspaceProps> = ({
  onBack,
  locked = false,
  engineMessage,
  onRetryEngine,
  pdfReferenceSource = null,
  onOpenPdfReference,
}) => {
  const [boards, setBoards] = useState<BoardDocument[]>([]);
  const [activeBoardId, setActiveBoardId] = useState('');
  const [projects, setProjects] = useState<BoardProject[]>([]);
  const [projectIdByBoardId, setProjectIdByBoardId] = useState<Map<string, string>>(() => new Map());
  const [activeProjectId, setActiveProjectId] = useState('');
  const [projectReferences, setProjectReferences] = useState<PdfReference[]>([]);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [projectLoadAttempt, setProjectLoadAttempt] = useState(0);
  const [projectDialog, setProjectDialog] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [renamingProject, setRenamingProject] = useState(false);
  const [projectDraft, setProjectDraft] = useState('');
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);
  const projectMenuRef = useRef<HTMLDivElement>(null);
  const [moveDialog, setMoveDialog] = useState(false);
  const [moveTargetId, setMoveTargetId] = useState('');
  const [deleteProjectId, setDeleteProjectId] = useState<string | null>(null);
  const [deleteProjectDraft, setDeleteProjectDraft] = useState('');
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [spacePanActive, setSpacePanActive] = useState(false);
  const spaceHeld = useRef(false);
  const [pdfReferenceDialog, setPdfReferenceDialog] = useState(false);
  const [pdfReferenceQuote, setPdfReferenceQuote] = useState('');
  const [pdfReferenceNote, setPdfReferenceNote] = useState('');
  const [referencesOpen, setReferencesOpen] = useState(false);
  /** Ritual «Volver a mirar»: propuestas que aún no tocan el referente. */
  const [mirarOpen, setMirarOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const writes = useBoardWrites();
  const saveState = writes.error ? 'error' : writes.pending > 0 ? 'saving' : 'saved';
  const [loadError, setLoadError] = useState<string | null>(null);
  const storageError = loadError ?? writes.error;
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([]);
  /** Copia viva para que los callbacks de tarjeta no cambien de identidad con cada selección. */
  const selectedIdsRef = useRef<string[]>([]);
  useEffect(() => { selectedIdsRef.current = selectedCardIds; }, [selectedCardIds]);
  const [connectMode, setConnectMode] = useState(false);
  const [connectFromId, setConnectFromId] = useState<string | null>(null);
  /** Tirador de conector: tarjeta de origen y puntero en coordenadas de pantalla. */
  const [connectDraft, setConnectDraft] = useState<{ from: string; x: number; y: number; mundo: { x: number; y: number }; target: string | null } | null>(null);
  const [marquee, setMarquee] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [nestedDialog, setNestedDialog] = useState(false);
  const [templateDialog, setTemplateDialog] = useState(false);
  const [templates, setTemplates] = useState<Plantilla[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  /** Aviso de borrado con deshacer: la red de seguridad es el historial, no un diálogo. */
  const [aviso, setAviso] = useState<{ texto: string; deshacer?: () => void; historial?: boolean } | null>(null);
  const avisoTimer = useRef<number | null>(null);
  /** El listener se registra una vez; cada render actualiza el despachador con el estado vigente. */
  const ejecutarAtajoRef = useRef<(atajo: AtajoLienzo, event: KeyboardEvent) => void>(() => {});
  const [search, setSearch] = useState('');
  const [searchScope, setSearchScope] = useState<'tablero' | 'proyecto' | 'biblioteca'>('tablero');
  const [searchActivo, setSearchActivo] = useState(0);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [indexOpen, setIndexOpen] = useState(false);
  const [indexQuery, setIndexQuery] = useState('');
  const [indexScroll, setIndexScroll] = useState(0);
  const indexSearchRef = useRef<HTMLInputElement>(null);
  const pendingCentro = useRef<{ boardId: string; cardId: string } | null>(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  /** Engranaje de una tarjeta seleccionada: edita esa tarjeta o toda la selección. */
  const [settingsCardId, setSettingsCardId] = useState<string | null>(null);
  const [settingsPos, setSettingsPos] = useState<{ x: number; y: number } | null>(null);
  const [boardSettingsOpen, setBoardSettingsOpen] = useState(false);
  /** Punto donde estaba el cursor al pulsar N: la herramienta nace ahí, no en el centro. */
  const addPointRef = useRef<{ x: number; y: number } | null>(null);
  const linkPointRef = useRef<{ x: number; y: number } | null>(null);
  const mediaPointRef = useRef<{ x: number; y: number } | null>(null);
  const desarmarRef = useRef<(cardId: string, url: string) => void>(() => undefined);
  const adjuntarRef = useRef<(cardId: string, files: File[]) => void>(() => undefined);
  const capturarUrlRef = useRef<(cardId: string, url: string) => void>(() => undefined);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [libraryMenuOpen, setLibraryMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const libraryMenuRef = useRef<HTMLDivElement>(null);
  const [linkDialog, setLinkDialog] = useState(false);
  const [linkTitle, setLinkTitle] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  /** Modo Mano: un dedo o el ratón mueven el mundo sin dibujar marquesina. */
  const [handMode, setHandMode] = useState(false);
  const [guias, setGuias] = useState<GuiasIman>({});
  const [viewportSize, setViewportSize] = useState({ width: 0, height: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const relationsRef = useRef<SVGGElement>(null);
  const boardsRef = useRef<BoardDocument[]>([]);
  const activeBoardRef = useRef<BoardDocument | null>(null);
  const zoomValueRef = useRef<HTMLButtonElement>(null);
  const cameraRef = useRef({ pan: { x: 0, y: 0 }, zoom: 1 });
  /** T-3: último LOD aplicado, para registrar cada cambio (compacto ↔ completo). */
  const lodRef = useRef<'min' | 'full' | null>(null);
  /**
   * T-3 · el LOD no se cambia de golpe: con 500 tarjetas, montar todo el
   * contenido en un commit era un congelón de 145–538 ms al cruzar el 35 %.
   * `lodCompletas` guarda los ids con contenido completo: solo los que están
   * en el encuadre (más margen), y entran por tandas.
   */
  const [lodCompletas, setLodCompletas] = useState<Set<string>>(() => new Set());
  const lodCompletasRef = useRef<Set<string>>(new Set());
  /** T-3 · el LOD espera a que el zoom se asiente: una ráfaga +/− no monta nada. */
  const [zoomLod, setZoomLod] = useState(1);
  useEffect(() => {
    const timer = window.setTimeout(() => setZoomLod(zoom), 200);
    return () => window.clearTimeout(timer);
  }, [zoom]);
  const paintRaf = useRef(0);
  const inertiaRaf = useRef(0);
  const syncTimer = useRef<number | null>(null);
  /** Timer que retira `.gesto-activo` cuando dejan de llegar eventos de gesto. */
  const gestoVisualTimer = useRef<number | null>(null);
  const panDrag = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number; samples: MuestraInercia[]; captureEl: HTMLElement | null } | null>(null);
  const cardDrag = useRef<{ pointerId: number; boardId: string; ids: string[]; x: number; y: number; positions: Map<string, { x: number; y: number }>; sizes: Map<string, CardSize>; startBoard: BoardDocument; gesture: string; moved: boolean; captureEl: HTMLElement | null; lastX: number; lastY: number; lastT: number; altKey: boolean; duplicated: boolean } | null>(null);
  /** Rectángulo de selección (arrastrar el fondo), en coordenadas de pantalla. */
  const marqueeDrag = useRef<{ pointerId: number; startX: number; startY: number; captureEl: HTMLElement | null; modo: 'reemplazar' | 'sumar' | 'restar' } | null>(null);
  /** H3 · dedos activos y gesto táctil: un dedo dibuja, dos panean y pellizcan. */
  const touchPoints = useRef(new Map<number, { x: number; y: number }>());
  const touchGesture = useRef<{
    mode: 'marquee' | 'camera';
    baseCamera?: { pan: { x: number; y: number }; zoom: number };
    baseDist?: number;
    baseMid?: { x: number; y: number };
  } | null>(null);
  const touchIgnore = useRef(false);
  const connectOrigin = useRef<{ cardId: string; pointerId: number } | null>(null);
  /** Herramienta de marco elegida en el menú: el siguiente arrastre dibuja el rectángulo. */
  const [frameToolId, setFrameToolId] = useState<string | null>(null);
  const [frameDraft, setFrameDraft] = useState<FrameRect | null>(null);
  const [draggingIds, setDraggingIds] = useState<string[]>([]);
  const [settlingIds, setSettlingIds] = useState<string[]>([]);
  const [dropFrameId, setDropFrameId] = useState<string | null>(null);
  const dropFrameIdRef = useRef<string | null>(null);
  const frameResize = useRef<{ pointerId: number; cardId: string; tipo: 'marco' | 'columna'; dir: string; startX: number; startY: number; x: number; y: number; width: number; height: number; startBoard: BoardDocument; captureEl: HTMLElement | null; elemento: HTMLElement | null; raf: number; ultimo: { x: number; y: number; width: number; height: number } } | null>(null);
  const freeResize = useRef<{ pointerId: number; cardId: string; corner: EsquinaMedia; startX: number; startY: number; x: number; y: number; width: number; height: number; ratio: number; startBoard: BoardDocument; captureEl: HTMLElement | null; elemento: HTMLElement | null; raf: number; ultimo: { x: number; y: number; width: number; height: number } | null } | null>(null);
  /** H6 · asa de ancho para notas y selección múltiple; el alto sigue al contenido. */
  const widthResize = useRef<{ pointerId: number; ids: string[]; startX: number; startWidths: Map<string, number>; startBoard: BoardDocument; captureEl: HTMLElement | null; raf: number; ultimas: Map<string, number> } | null>(null);
  const settleTimer = useRef<number | null>(null);
  const frameDraw = useRef<{ pointerId: number; start: { x: number; y: number }; captureEl: HTMLElement | null } | null>(null);
  const wheelHandlerRef = useRef<(event: WheelEvent) => void>(() => {});
  /** Marco abierto a pantalla completa en la vista Archivo; Esc vuelve a la pizarra. */
  const [archiveFullscreenId, setArchiveFullscreenId] = useState<string | null>(null);
  /** Marco cuya publicación local se está escribiendo (bloquea el botón mientras dura). */
  const [publishingFrameId, setPublishingFrameId] = useState<string | null>(null);
  /** El manifiesto semanal espera al motor local; el botón no se dispara dos veces. */
  const [manifesting, setManifesting] = useState(false);
  const [propuestaManifiesto, setPropuestaManifiesto] = useState<{ frame: BoardCard; cards: BoardCard[] } | null>(null);
  const [boardHistories, setBoardHistories] = useState<Record<string, BoardHistory>>({});
  /** «nueva» declara que no había historial que restaurar; «restaurada» que sí. */
  const [historyStatus, setHistoryStatus] = useState<'nueva' | 'restaurada'>('nueva');
  const historiesReady = useRef(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [borrados, setBorrados] = useState<BorradoEntry[]>([]);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  /** Un clic que llega después de arrastrar o de un gesto con modificador no debe cambiar la selección otra vez. */
  const suppressCardClick = useRef(false);
  /** El clic posterior a dibujar un marco no debe vaciar la selección recién creada. */
  const suppressViewportClick = useRef(false);
  /** Cada salida de un campo de texto cierra el grupo de deshacer de esa escritura. */
  const textSession = useRef(0);
  const closeTextGroup = () => {
    textSession.current += 1;
  };
  const initializedCamera = useRef(false);
  const previousBoardId = useRef('');
  const importInput = useRef<HTMLInputElement>(null);
  const mediaInput = useRef<HTMLInputElement>(null);
  const gustosInput = useRef<HTMLInputElement>(null);
  /** Referente bajo el puntero: una URL de imagen pegada cae en él. */
  const hoveredReferenteId = useRef<string | null>(null);
  /** Último punto del mundo bajo el puntero: pegar crea aquí, no en el centro. */
  const lastPointerWorld = useRef<{ x: number; y: number } | null>(null);
  const cardHandlers = useRef<CardHandlers | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const algunDialogoAbierto = shortcutsOpen || nestedDialog || templateDialog || linkDialog || projectDialog || pdfReferenceDialog || archiveOpen || moveDialog || Boolean(archiveFullscreenId);
  useFocusTrap(algunDialogoAbierto, dialogRef);

  const projectBoards = activeProjectId
    ? boards.filter((board) => projectIdByBoardId.get(board.id) === activeProjectId)
    : boards;
  const projectOptions = projects.filter((project) => !project.archivado);
  const archivedProjects = projects.filter((project) => project.archivado);
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const activeProjectReferences = projectReferences.filter((reference) => reference.projectId === activeProjectId);
  const activeBoard = projectBoards.find((board) => board.id === activeBoardId) ?? projectBoards[0] ?? null;
  const ajustes: BoardSettings = activeBoard?.ajustes ?? DEFAULT_BOARD_SETTINGS;
  const snapEnabled = ajustes.iman;
  const selectedCards = activeBoard?.cards.filter((card) => selectedCardIds.includes(card.id)) ?? [];
  /** T-3: el `contain: paint` del escenario solo se retira si hay coordenadas negativas. */
  const hasNegative = (activeBoard?.cards ?? []).some((card) => card.x < 0 || card.y < 0);
  const containRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (containRef.current === hasNegative) return;
    marca('contain:cambio', `${containRef.current === null ? 'inicio' : containRef.current ? 'negativo' : 'positivo'} → ${hasNegative ? 'negativo' : 'positivo'}`);
    containRef.current = hasNegative;
  }, [hasNegative]);
  const activeHistory = activeBoard ? boardHistories[activeBoard.id] ?? emptyBoardHistory() : emptyBoardHistory();
  const canUndo = activeHistory.undo.length > 0;
  const canRedo = activeHistory.redo.length > 0;

  const cardsById = useMemo(() => new Map((activeBoard?.cards ?? []).map((card) => [card.id, card])), [activeBoard]);
  /** Hijos que ya se pintan dentro de un marco con vista propia: no se dibujan dos veces. */
  const framedChildIds = useMemo(() => {
    const ids = new Set<string>();
    for (const card of activeBoard?.cards ?? []) {
      if (card.type === 'columna') {
        for (const id of readColumnData(card).hijos) ids.add(id);
        continue;
      }
      if (card.type !== 'marco' || readFrameData(card).vista === 'libre') continue;
      for (const id of readFrameData(card).hijos) ids.add(id);
    }
    for (const id of columnChildIds(activeBoard?.cards ?? [])) ids.add(id);
    return ids;
  }, [activeBoard]);
  const archiveFullscreenFrame = archiveFullscreenId
    ? activeBoard?.cards.find((card) => card.id === archiveFullscreenId && card.type === 'marco') ?? null
    : null;

  /** Referentes de todo el proyecto: son las fuentes posibles de una tirada de Entropía. */
  const fuentesEntropia = useMemo<FuenteEntropia[]>(() => {
    const sourceBoards = projectBoards.length ? projectBoards : activeBoard ? [activeBoard] : [];
    const vistas = new Set<string>();
    const fuentes: FuenteEntropia[] = [];
    for (const board of sourceBoards) {
      for (const card of board.cards) {
        if (card.type !== 'referente' || vistas.has(card.id)) continue;
        vistas.add(card.id);
        const referente = leerReferente(card);
        const imagen = referente.imagenes[0];
        fuentes.push({
          id: card.id,
          nombre: referente.nombre || card.title || 'Referente sin nombre',
          etiquetas: referente.etiquetas,
          ...(imagen ? { imagen: { src: imagen.dataUrl, nombre: imagen.name } } : {}),
        });
      }
    }
    return fuentes;
  }, [projectBoards, activeBoard]);

  const leaveBoard = async () => {
    // Salir con cambios que no están confirmados en el almacenamiento sería perderlos: se queda y se explica.
    const saved = await flushBoardWrites();
    if (!saved) {
      setNotice('No se pudo guardar el tablero. Tus cambios siguen aquí: reintenta o exporta una copia antes de salir.');
      return;
    }
    onBack();
  };

  useEffect(() => {
    let current = true;
    Promise.all([loadBoardWorkspace(), leerHistoriales()])
      .then(([snapshot, historiales]) => {
        if (!current) return;
        if (snapshot.boards.length) {
          setBoards(snapshot.boards);
          setActiveBoardId(snapshot.activeBoardId ?? snapshot.boards[0].id);
        } else {
          const first = createBoard('Mi tablero');
          setBoards([first]);
          setActiveBoardId(first.id);
          enqueueBoardSave(first, { immediate: true });
        }
        const ids = new Set(snapshot.boards.map((board) => board.id));
        const restaurados = Object.fromEntries(
          Object.entries(historiales).filter(([boardId]) => ids.has(boardId)),
        );
        if (Object.keys(restaurados).length > 0) {
          setBoardHistories(restaurados);
          setHistoryStatus('restaurada');
        } else {
          setHistoryStatus('nueva');
        }
        historiesReady.current = true;
        if (snapshot.skipped.length) {
          const count = snapshot.skipped.length;
          setNotice(`${count === 1 ? 'Un tablero no se pudo abrir' : `${count} tableros no se pudieron abrir`} y se conserva sin cambios: ${snapshot.skipped[0].reason}`);
        }
        setLoaded(true);
      })
      .catch((error: unknown) => {
        if (!current) return;
        setLoadError(error instanceof Error ? error.message : 'El almacenamiento local no está disponible.');
        const first = createBoard('Mi tablero');
        setBoards([first]);
        setActiveBoardId(first.id);
        setLoaded(true);
      });
    return () => {
      current = false;
    };
  }, []);

  // El historial de deshacer sobrevive a recargar. Se escribe con pausa y por
  // tablero activo: guardar la copia de los 500 tableros en cada gesto sería peor
  // que el problema que resuelve.
  useEffect(() => {
    if (!loaded || !historiesReady.current || !activeBoardId) return;
    const inicio = marca('historial:programado', `${activeBoardId} · ${(boardHistories[activeBoardId]?.undo.length ?? 0)} pasos`);
    const timer = window.setTimeout(() => {
      const history = boardHistories[activeBoardId];
      if (history) {
        marcaFin('historial:espera', inicio);
        void guardarHistorial(activeBoardId, history);
      }
    }, 600);
    return () => window.clearTimeout(timer);
  }, [activeBoardId, boardHistories, loaded]);

  const projectBoardIds = useMemo(() => boards.map((board) => board.id).sort(), [boards]);
  const projectBoardSignature = JSON.stringify(projectBoardIds);
  const loadedProjectBoardSignature = useRef('');

  // Proyectos y referencias viven en una base aditiva separada: los registros existentes de tableros no se reescriben.
  useEffect(() => {
    if (!loaded || !projectBoardSignature || loadedProjectBoardSignature.current === projectBoardSignature) return;
    loadedProjectBoardSignature.current = projectBoardSignature;
    let current = true;
    loadProjectWorkspace(projectBoardIds)
      .then((workspace) => {
        if (!current) return;
        setProjects(workspace.projects);
        setProjectIdByBoardId(workspace.projectIdByBoardId);
        setProjectReferences(workspace.references);
        const proyectoActivo = workspace.projects.find((project) => project.id === workspace.activeProjectId) ?? null;
        const destinoId = proyectoActivo && !proyectoActivo.archivado
          ? workspace.activeProjectId
          : workspace.projects.find((project) => !project.archivado)?.id ?? workspace.activeProjectId;
        setActiveProjectId(destinoId);
        if (destinoId !== workspace.activeProjectId) void setActiveProject(destinoId).catch(() => undefined);
        const selected = boards.find((board) =>
          board.id === activeBoardId && workspace.projectIdByBoardId.get(board.id) === destinoId,
        ) ?? boards.find((board) => workspace.projectIdByBoardId.get(board.id) === destinoId);
        if (selected) setActiveBoardId(selected.id);
        setProjectError(null);
        if (workspace.skipped.length) {
          const first = workspace.skipped[0];
          setNotice(`${workspace.skipped.length === 1 ? 'Un registro de proyecto no se pudo abrir' : `${workspace.skipped.length} registros de proyecto no se pudieron abrir`} y se conservan sin cambios: ${first.reason}`);
        } else if (workspace.migration.linkedExistingBoards > 0) {
          const count = workspace.migration.linkedExistingBoards;
          setNotice(`${count === 1 ? 'Tu tablero existente quedó' : `Tus ${count} tableros existentes quedaron`} organizado${count === 1 ? '' : 's'} en Proyecto general, sin reescribir su contenido.`);
        }
      })
      .catch((error: unknown) => {
        if (!current) return;
        loadedProjectBoardSignature.current = '';
        setProjectError(error instanceof Error ? error.message : 'No se pudieron abrir los proyectos locales.');
        setActiveProjectId('');
        setProjectIdByBoardId(new Map());
      });
    return () => {
      current = false;
    };
  }, [activeBoardId, boards, loaded, projectBoardIds, projectBoardSignature, projectLoadAttempt]);

  // El viewport sólo existe después de la carga: el efecto se vuelve a ejecutar cuando aparece.
  useLayoutEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const resize = () => setViewportSize({ width: element.clientWidth, height: element.clientHeight });
    resize();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    observer?.observe(element);
    window.addEventListener('resize', resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', resize);
    };
  }, [loaded]);

  // Tamaños reales de las tarjetas en unidades del mundo (no dependen del zoom actual).
  const measureCardSizes = useCallback((): Map<string, CardSize> => {
    const elements = viewportRef.current?.querySelectorAll<HTMLElement>('[data-card-id]') ?? [];
    return new Map(Array.from(elements).flatMap((element) => {
      const id = element.dataset.cardId;
      if (!id) return [];
      const bounds = element.getBoundingClientRect();
      return [[id, { width: bounds.width / cameraRef.current.zoom, height: bounds.height / cameraRef.current.zoom }] as const];
    }));
  }, []);

  const aplicarCamara = useCallback(() => {
    const { pan: posicion, zoom: escala } = cameraRef.current;
    const stage = stageRef.current;
    if (stage) {
      stage.style.transform = `translate3d(${posicion.x}px, ${posicion.y}px, 0) scale(${escala})`;
      // T-3: el atributo es para medios/marcos; el contenido de las tarjetas
      // cambia por tandas en React, nunca con un recálculo global.
      const lod: 'min' | 'full' = escala < 0.35 ? 'min' : 'full';
      if (stage.dataset.lod !== lod) {
        stage.dataset.lod = lod;
        marca('lod:cambio', `${lodRef.current ?? 'inicio'} → ${lod} · ${Math.round(escala * 100)} % · ${lodCompletasRef.current.size}/${activeBoardRef.current?.cards.length ?? 0} completas`);
      }
      lodRef.current = lod;
    }
    const viewport = viewportRef.current;
    if (viewport) {
      viewport.style.backgroundPosition = `${posicion.x}px ${posicion.y}px`;
      viewport.style.backgroundSize = `${GRID_SIZE * escala}px ${GRID_SIZE * escala}px`;
    }
    relationsRef.current?.setAttribute('transform', `translate(${posicion.x} ${posicion.y}) scale(${escala})`);
    if (zoomValueRef.current) {
      zoomValueRef.current.textContent = `${Math.round(escala * 100)}%`;
      zoomValueRef.current.setAttribute('aria-label', `Zoom ${Math.round(escala * 100)} por ciento, ajustar tablero`);
    }
  }, []);

  const pintarCamara = useCallback(() => {
    if (paintRaf.current) return;
    paintRaf.current = requestAnimationFrame(() => {
      paintRaf.current = 0;
      aplicarCamara();
    });
  }, [aplicarCamara]);

  const sincronizarCamara = useCallback(() => {
    if (syncTimer.current) {
      window.clearTimeout(syncTimer.current);
      syncTimer.current = null;
    }
    setPan(cameraRef.current.pan);
    setZoom(cameraRef.current.zoom);
  }, []);

  const programarSincronizacion = useCallback(() => {
    if (syncTimer.current) window.clearTimeout(syncTimer.current);
    syncTimer.current = window.setTimeout(() => {
      syncTimer.current = null;
      sincronizarCamara();
    }, 150);
  }, [sincronizarCamara]);

  /**
   * Mientras hay gesto, ninguna transición CSS puede tocar transform/scale de las
   * tarjetas ni del mundo. La clase vive en el DOM (no en React) para no re-renderizar.
   */
  const marcarGestoVisual = useCallback((duracionMs = 0) => {
    viewportRef.current?.classList.add('gesto-activo');
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    if (duracionMs > 0) {
      gestoVisualTimer.current = window.setTimeout(() => {
        gestoVisualTimer.current = null;
        viewportRef.current?.classList.remove('gesto-activo');
      }, duracionMs);
    }
  }, []);

  const terminarGestoVisual = useCallback(() => {
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    viewportRef.current?.classList.remove('gesto-activo');
  }, []);

  const detenerInercia = useCallback(() => {
    if (inertiaRaf.current) {
      cancelAnimationFrame(inertiaRaf.current);
      inertiaRaf.current = 0;
    }
  }, []);

  const iniciarInercia = useCallback((vx: number, vy: number) => {
    detenerInercia();
    if (movimientoReducido() || Math.hypot(vx, vy) < 80) return;
    let estado = { x: cameraRef.current.pan.x, y: cameraRef.current.pan.y, vx, vy };
    let ultimo = performance.now();
    const paso = (ahora: number) => {
      const dt = Math.min(0.05, Math.max(0, (ahora - ultimo) / 1000));
      ultimo = ahora;
      estado = pasoInercia(estado, dt);
      cameraRef.current = { ...cameraRef.current, pan: { x: estado.x, y: estado.y } };
      pintarCamara();
      if (estado.vx !== 0 || estado.vy !== 0) inertiaRaf.current = requestAnimationFrame(paso);
      else {
        inertiaRaf.current = 0;
        programarSincronizacion();
      }
    };
    inertiaRaf.current = requestAnimationFrame(paso);
  }, [detenerInercia, pintarCamara, programarSincronizacion]);

  const limpiarInclinacion = useCallback(() => {
    viewportRef.current?.style.removeProperty('--drag-tilt');
  }, []);

  /** Un gesto nuevo o una pérdida de foco no deja capturas, clases ni timers colgados. */
  const cancelarGestos = useCallback(() => {
    detenerInercia();
    if (gestoVisualTimer.current) {
      window.clearTimeout(gestoVisualTimer.current);
      gestoVisualTimer.current = null;
    }
    if (settleTimer.current) {
      window.clearTimeout(settleTimer.current);
      settleTimer.current = null;
    }
    const pan = panDrag.current;
    if (pan) liberarPuntero(pan.captureEl, pan.pointerId);
    const card = cardDrag.current;
    if (card) liberarPuntero(card.captureEl, card.pointerId);
    const draw = frameDraw.current;
    if (draw) liberarPuntero(draw.captureEl, draw.pointerId);
    const resize = frameResize.current;
    if (resize) {
      liberarPuntero(resize.captureEl, resize.pointerId);
      if (resize.raf) cancelAnimationFrame(resize.raf);
      if (resize.elemento) {
        resize.elemento.style.left = `${resize.x}px`;
        resize.elemento.style.top = `${resize.y}px`;
        resize.elemento.style.width = `${resize.width}px`;
        resize.elemento.style.height = `${resize.height}px`;
      }
    }
    const anchos = widthResize.current;
    if (anchos) {
      liberarPuntero(anchos.captureEl, anchos.pointerId);
      if (anchos.raf) cancelAnimationFrame(anchos.raf);
      for (const [id, ancho] of anchos.startWidths) {
        const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${id}"]`);
        if (elemento) elemento.style.width = `${ancho}px`;
      }
    }
    const free = freeResize.current;
    if (free) {
      liberarPuntero(free.captureEl, free.pointerId);
      if (free.raf) cancelAnimationFrame(free.raf);
      if (free.elemento) {
        free.elemento.style.left = `${free.x}px`;
        free.elemento.style.top = `${free.y}px`;
        free.elemento.style.width = `${free.width}px`;
        free.elemento.style.height = `${free.height}px`;
      }
    }
    const marquesina = marqueeDrag.current;
    if (marquesina) liberarPuntero(marquesina.captureEl, marquesina.pointerId);
    panDrag.current = null;
    cardDrag.current = null;
    frameDraw.current = null;
    frameResize.current = null;
    freeResize.current = null;
    widthResize.current = null;
    marqueeDrag.current = null;
    touchPoints.current.clear();
    touchGesture.current = null;
    touchIgnore.current = false;
    connectOrigin.current = null;
    setConnectDraft(null);
    setIsPanning(false);
    setDraggingIds([]);
    setSettlingIds([]);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
    setFrameDraft(null);
    setMarquee(null);
    setGuias({});
    limpiarInclinacion();
    terminarGestoVisual();
  }, [detenerInercia, limpiarInclinacion, terminarGestoVisual]);

  useLayoutEffect(() => {
    aplicarCamara();
  });

  // Los guardados asíncronos (vista previa, lectura, referente) necesitan el tablero más reciente,
  // no el de la renderización en la que se lanzó la petición.
  useLayoutEffect(() => {
    boardsRef.current = boards;
    activeBoardRef.current = activeBoard;
  }, [activeBoard, boards]);

  useEffect(() => () => {
    if (paintRaf.current) cancelAnimationFrame(paintRaf.current);
    if (inertiaRaf.current) cancelAnimationFrame(inertiaRaf.current);
    if (syncTimer.current) window.clearTimeout(syncTimer.current);
    if (gestoVisualTimer.current) window.clearTimeout(gestoVisualTimer.current);
  }, []);

  // El tablero cambia de vista o de documento: nada del gesto anterior debe sobrevivir.
  useEffect(() => () => cancelarGestos(), [activeBoard?.id, archiveFullscreenId, cancelarGestos]);

  // Red de seguridad para cuando el pointerup ocurre fuera de la ventana o el WebView pierde el foco.
  useEffect(() => {
    const alSoltar = () => {
      if (panDrag.current || cardDrag.current || frameDraw.current || frameResize.current || freeResize.current || widthResize.current || marqueeDrag.current) cancelarGestos();
    };
    const alOcultar = () => { if (document.hidden) alSoltar(); };
    window.addEventListener('pointerup', alSoltar);
    window.addEventListener('pointercancel', alSoltar);
    window.addEventListener('blur', alSoltar);
    document.addEventListener('visibilitychange', alOcultar);
    return () => {
      window.removeEventListener('pointerup', alSoltar);
      window.removeEventListener('pointercancel', alSoltar);
      window.removeEventListener('blur', alSoltar);
      document.removeEventListener('visibilitychange', alOcultar);
    };
  }, [cancelarGestos]);

  const centerCamera = useCallback((board: BoardDocument | null) => {
    const { width, height } = viewportSize;
    if (!width || !height) return;
    const camera = fitBoardCamera(board?.cards ?? [], { width, height }, measureCardSizes());
    cameraRef.current = camera;
    aplicarCamara();
    setZoom(camera.zoom);
    setPan(camera.pan);
  }, [aplicarCamara, measureCardSizes, viewportSize]);

  useEffect(() => {
    if (!viewportSize.width || !viewportSize.height) return;
    if (!initializedCamera.current) {
      initializedCamera.current = true;
      centerCamera(null);
    }
  }, [centerCamera, viewportSize]);

  useEffect(() => {
    if (!loaded || !activeBoard || !viewportSize.width || !viewportSize.height) return;
    if (!previousBoardId.current || previousBoardId.current !== activeBoard.id) centerCamera(activeBoard);
    previousBoardId.current = activeBoard.id;
  }, [activeBoard, centerCamera, loaded, viewportSize]);

  /**
   * T-3 · el contenido completo entra por tandas y solo para lo que está en el
   * encuadre (más un margen). 500 tarjetas completas de golpe eran 238 ms de
   * estilo/layout; 4 por fotograma mantienen cada frame dentro de presupuesto.
   */
  useEffect(() => {
    const tablero = activeBoard;
    const { width, height } = viewportSize;
    const escala = Math.max(zoomLod, 0.0001);
    const deseados: string[] = [];
    if (tablero && width && height && zoom >= 0.35 && zoomLod >= 0.35) {
      const margen = 512;
      const izquierda = -pan.x / escala - margen;
      const arriba = -pan.y / escala - margen;
      const derecha = (width - pan.x) / escala + margen;
      const abajo = (height - pan.y) / escala + margen;
      const centro = { x: (izquierda + derecha) / 2, y: (arriba + abajo) / 2 };
      const candidatos: Array<{ id: string; distancia: number }> = [];
      for (const card of tablero.cards) {
        const rect = rectDeTarjeta(card);
        if (rect.x > derecha || rect.y > abajo || rect.x + rect.width < izquierda || rect.y + rect.height < arriba) continue;
        const dx = rect.x + rect.width / 2 - centro.x;
        const dy = rect.y + rect.height / 2 - centro.y;
        candidatos.push({ id: card.id, distancia: dx * dx + dy * dy });
      }
      candidatos.sort((a, b) => a.distancia - b.distancia);
      deseados.push(...candidatos.map((candidato) => candidato.id));
    }
    const objetivo = new Set(deseados);
    let raf = 0;
    let cancelado = false;
    const paso = () => {
      if (cancelado) return;
      const actual = lodCompletasRef.current;
      const faltan = deseados.filter((id) => !actual.has(id));
      const sobran = [...actual].filter((id) => !objetivo.has(id));
      if (!faltan.length && !sobran.length) return;
      const siguiente = new Set(actual);
      if (faltan.length) {
        for (const id of faltan.slice(0, 4)) siguiente.add(id);
        marca('lod:tanda', `+${Math.min(4, faltan.length)} · ${siguiente.size}/${deseados.length} en encuadre`);
      } else {
        for (const id of sobran.slice(0, 16)) siguiente.delete(id);
        marca('lod:tanda', `−${Math.min(16, sobran.length)} · ${siguiente.size}/${deseados.length} en encuadre`);
      }
      lodCompletasRef.current = siguiente;
      setLodCompletas(siguiente);
      raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => {
      cancelado = true;
      if (raf) cancelAnimationFrame(raf);
    };
  }, [activeBoard, pan, viewportSize, zoom, zoomLod]);

  useEffect(() => {
    if (!loaded || !activeBoardId) return;
    rememberActiveBoard(activeBoardId);
  }, [activeBoardId, loaded]);

  // Las plantillas guardadas ya no viven en localStorage global: la primera vez que
  // aparece un proyecto se mueven a su registro y se borra la copia antigua.
  const migratedTemplates = useRef(false);
  useEffect(() => {
    if (!loaded || !activeProject || migratedTemplates.current) return;
    const legacy = leerPlantillasLegacy();
    if (legacy.length === 0) return;
    migratedTemplates.current = true;
    const projectId = activeProject.id;
    void (async () => {
      try {
        const plantillas = await addProjectPlantillas(projectId, legacy);
        borrarPlantillasLegacy();
        setProjects((current) => current.map((project) => project.id === projectId ? { ...project, plantillas } : project));
        setTemplates(listarPlantillas(plantillas));
        setNotice(`${legacy.length} ${legacy.length === 1 ? 'plantilla guardada se movió' : 'plantillas guardadas se movieron'} a «${activeProject.name}».`);
      } catch (error) {
        migratedTemplates.current = false;
        setProjectError(error instanceof Error ? error.message : 'No se pudieron mover las plantillas al proyecto.');
      }
    })();
  }, [activeProject, loaded]);

  // El sistema de diseño del tablero se aplica en la raíz para que alcance
  // también a los portales (pliego, caja de luz, diálogos), no solo al lienzo.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.designSystem = normalizeDesignSystem(activeBoard?.sistema);
    return () => {
      delete root.dataset.designSystem;
    };
  }, [activeBoard?.id, activeBoard?.sistema]);

  // Un tablero anidado pide abrirse desde su tarjeta (botón o doble clic).
  useEffect(() => {
    const abrir = (event: Event) => {
      const boardId = (event as CustomEvent<{ boardId?: string }>).detail?.boardId;
      if (!boardId) return;
      const destino = boards.find((board) => board.id === boardId);
      if (!destino) {
        setNotice('Ese tablero anidado ya no existe. La tarjeta conserva su referencia.');
        return;
      }
      void (async () => {
        const guardado = await flushBoardWrites();
        if (!guardado) {
          setNotice('No se abrió el tablero anidado porque el actual aún no se pudo guardar.');
          return;
        }
        const proyecto = projectIdByBoardId.get(boardId);
        if (proyecto && proyecto !== activeProjectId) {
          try {
            await setActiveProject(proyecto);
            setActiveProjectId(proyecto);
          } catch {
            /* El tablero se abre igual: el vínculo de proyecto no bloquea la lectura. */
          }
        }
        setActiveBoardId(boardId);
        setSelectedCardIds([]);
      })();
    };
    window.addEventListener(ABRIR_TABLERO_EVENT, abrir);
    return () => window.removeEventListener(ABRIR_TABLERO_EVENT, abrir);
  }, [activeProjectId, boards, projectIdByBoardId]);

  const updateBoard = useCallback((
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    const actual = activeBoardRef.current ?? boardsRef.current.find((board) => board.id === activeBoardId);
    if (!actual) return;
    const nextBoard = { ...mutate(actual), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      marca('historial:registro', `${nextBoard.id} · ${nextBoard.cards.length} tarjetas · ${options.coalesceKey ?? 'sin coalescencia'}`);
      setBoardHistories((current) => ({
        ...current,
        [actual.id]: recordBoardChange(current[actual.id] ?? emptyBoardHistory(), actual, nextBoard, options.coalesceKey),
      }));
    }
    activeBoardRef.current = nextBoard;
    boardsRef.current = boardsRef.current.length
      ? boardsRef.current.map((board) => board.id === nextBoard.id ? nextBoard : board)
      : [nextBoard];
    enqueueBoardSave(nextBoard);
    setBoards(boardsRef.current);
  }, [activeBoardId]);

  /** Cada tablero guarda sus guías, imán, retícula, fondo, cursor y densidad. */
  const updateAjustes = useCallback((patch: Partial<BoardSettings>) => {
    updateBoard((board) => ({
      ...board,
      ajustes: { ...(board.ajustes ?? DEFAULT_BOARD_SETTINGS), ...patch },
    }), { coalesceKey: 'ajustes-tablero' });
  }, [updateBoard]);

  /** Una lectura aceptada puede caer en la Biblioteca aunque el tablero abierto sea otro. */
  const updateBoardById = useCallback((
    boardId: string,
    mutate: (board: BoardDocument) => BoardDocument,
    options: { recordHistory?: boolean; coalesceKey?: string } = {},
  ) => {
    const target = boardsRef.current.find((board) => board.id === boardId);
    if (!target) return;
    const nextBoard = { ...mutate(target), updatedAt: new Date().toISOString() };
    if (options.recordHistory !== false) {
      setBoardHistories((current) => ({
        ...current,
        [boardId]: recordBoardChange(current[boardId] ?? emptyBoardHistory(), target, nextBoard, options.coalesceKey),
      }));
    }
    boardsRef.current = boardsRef.current.map((board) => board.id === boardId ? nextBoard : board);
    if (activeBoardRef.current?.id === boardId) activeBoardRef.current = nextBoard;
    enqueueBoardSave(nextBoard);
    setBoards(boardsRef.current);
  }, []);

  const aceptarLecturaEnReferente = useCallback((boardId: string, cardId: string, lectura: Lectura) => {
    const nombre = boards
      .find((board) => board.id === boardId)
      ?.cards.find((card) => card.id === cardId)
      ?.title;
    updateBoardById(boardId, (board) => ({
      ...board,
      cards: board.cards.map((card) => card.id === cardId ? aceptarLectura(card, lectura) : card),
    }));
    setNotice(`Lectura aceptada y guardada en «${nombre || 'el referente'}».`);
  }, [boards, updateBoardById]);

  /** Crea una tarjeta con la herramienta del registro, en el centro de la vista. */
  const addToolCard = useCallback((toolId: string, configure?: (card: BoardCard) => void, at?: { x: number; y: number }): BoardCard | null => {
    const tool = getBoardTool(toolId);
    if (!activeBoard) return null;
    // El tablero más reciente: dos altas seguidas no deben colocar la segunda
    // usando la lista de tarjetas anterior.
    const boardActual = activeBoardRef.current ?? activeBoard;
    if (frameToolId) setNotice(null);
    setFrameToolId(null);
    setFrameDraft(null);
    frameDraw.current = null;
    if (!tool) {
      setNotice(`La herramienta «${toolId}» no está instalada.`);
      return null;
    }
    const destino = at ?? screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, cameraRef.current);
    let x = destino.x - 130;
    let y = destino.y - 90;
    const prototipo = tool.crear(0, 0) as BoardCard;
    const ancho = prototipo.width || 260;
    const alto = prototipo.type === 'marco' ? readFrameData(prototipo).alto : 200;
    if (!at) {
      // Una tarjeta nueva nunca tapa a otra ni cae fuera de la vista:
      // busca un rectángulo libre y, al llegar al borde, vuelve a la esquina visible.
      const visible = {
        izquierda: screenToWorld({ x: 72, y: 72 }, cameraRef.current).x,
        arriba: screenToWorld({ x: 72, y: 72 }, cameraRef.current).y,
        derecha: screenToWorld({ x: Math.max(72, viewportSize.width - 72), y: 72 }, cameraRef.current).x,
        abajo: screenToWorld({ x: 72, y: Math.max(72, viewportSize.height - 72) }, cameraRef.current).y,
      };
      const medidas = measureCardSizes();
      const libre = (candidatoX: number, candidatoY: number) => !boardActual.cards.some((item) => {
        const medida = medidas.get(item.id);
        const anchoItem = medida?.width ?? item.width;
        const altoItem = medida?.height ?? (item.type === 'marco'
          ? readFrameData(item).alto
          : item.type === 'columna'
            ? 260
            : item.height ?? 200);
        return candidatoX < item.x + anchoItem && candidatoX + ancho > item.x
          && candidatoY < item.y + altoItem && candidatoY + alto > item.y;
      });
      // Espiral desde el centro: el primer hueco visible sin tapar nada. Si el
      // tablero está lleno, cae arriba a la izquierda, que sigue siendo visible.
      const paso = 40;
      let colocado = false;
      for (let anillo = 0; anillo <= 18 && !colocado; anillo += 1) {
        for (let ix = -anillo; ix <= anillo && !colocado; ix += 1) {
          for (let iy = -anillo; iy <= anillo && !colocado; iy += 1) {
            if (Math.abs(ix) !== anillo && Math.abs(iy) !== anillo) continue;
            const candidatoX = x + ix * paso;
            const candidatoY = y + iy * paso;
            if (candidatoX < visible.izquierda || candidatoY < visible.arriba) continue;
            if (candidatoX + ancho > visible.derecha || candidatoY + alto > visible.abajo) continue;
            if (libre(candidatoX, candidatoY)) {
              x = candidatoX;
              y = candidatoY;
              colocado = true;
            }
          }
        }
      }
      if (!colocado) {
        x = visible.izquierda + 24;
        y = visible.arriba + 24;
      }
    }
    const card = tool.crear(x, y) as BoardCard;
    configure?.(card);
    updateBoard((board) => ({ ...board, cards: [...board.cards, card] }));
    setSelectedCardIds([card.id]);
    return card;
  }, [activeBoard, frameToolId, measureCardSizes, updateBoard, viewportSize]);

  const chooseTool = useCallback((toolId: string, at?: { x: number; y: number }) => {
    const punto = at ?? addPointRef.current ?? undefined;
    addPointRef.current = null;
    setAddMenuOpen(false);
    setFrameToolId(null);
    if (toolId === 'tablero') {
      setNestedDialog(true);
      return;
    }
    if (toolId === 'link') {
      linkPointRef.current = punto ?? null;
      setLinkDialog(true);
      setLinkError(null);
      return;
    }
    if (toolId === 'media') {
      mediaPointRef.current = punto ?? null;
      mediaInput.current?.click();
      return;
    }
    // Un clic añade ya: la nota, la columna o el marco nacen donde estaba el cursor.
    addToolCard(toolId, undefined, punto);
  }, [addToolCard]);

  const activarHerramienta = (toolId: string) => chooseTool(toolId);

  const startToolDrag = (toolId: string) => (event: React.DragEvent<HTMLButtonElement>) => {
    event.dataTransfer.setData('application/x-prometeo-tool', toolId);
    event.dataTransfer.effectAllowed = 'copy';
  };

  const dropTool = (event: React.DragEvent<HTMLDivElement>) => {
    if (!activeBoard) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const hijoColumna = event.dataTransfer.getData('application/x-prometeo-column-child');
    if (hijoColumna) {
      event.preventDefault();
      try {
        const { columnId, cardId } = JSON.parse(hijoColumna) as { columnId?: string; cardId?: string };
        if (columnId && cardId) {
          const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
          updateBoard((board) => {
            const conHijoFuera = quitarHijoDeColumna(board.cards, columnId, cardId);
            return {
              ...board,
              cards: conHijoFuera.map((card) => card.id === cardId ? { ...card, x: punto.x - card.width / 2, y: punto.y - 20 } : card),
            };
          });
          setSelectedCardIds([cardId]);
          setNotice('Tarjeta sacada de la columna. Su posición es la del cursor.');
        }
      } catch {
        /* un arrastre externo no se interpreta */
      }
      return;
    }
    const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    const medidas = measureCardSizes();
    const referente = (activeBoardRef.current?.cards ?? []).find((card) => {
      if (card.type !== 'referente') return false;
      const alto = medidas.get(card.id)?.height ?? 260;
      return punto.x >= card.x && punto.x <= card.x + card.width && punto.y >= card.y && punto.y <= card.y + alto;
    });
    const archivos = Array.from(event.dataTransfer.files ?? []);
    if (archivos.length) {
      event.preventDefault();
      if (referente) {
        adjuntarRef.current(referente.id, archivos);
        return;
      }
      archivos.forEach((file, indice) => {
        void addMedia(file, { x: punto.x + indice * 36, y: punto.y + indice * 28 });
      });
      return;
    }
    const urlSoltada = (event.dataTransfer.getData('text/uri-list') || event.dataTransfer.getData('text/plain') || '').split('\n')[0]?.trim() ?? '';
    if (referente && isSafeExternalUrl(urlSoltada)) {
      event.preventDefault();
      capturarUrlRef.current(referente.id, urlSoltada);
      return;
    }
    const toolId = event.dataTransfer.getData('application/x-prometeo-tool');
    if (!toolId) return;
    event.preventDefault();
    const tool = getBoardTool(toolId);
    if (tool?.tipo === 'marco') {
      setFrameToolId(null);
      addToolCard(toolId, undefined, punto);
      setNotice('Marco creado. Arrástralo por la cabecera o cambia de vista en su menú.');
      return;
    }
    addToolCard(toolId, undefined, punto);
  };

  const publicarSeleccion = () => {
    const marcoSeleccionado = selectedCards.find((card) => card.type === 'marco');
    if (!marcoSeleccionado) {
      setNotice('Selecciona un marco para publicar su vista actual.');
      return;
    }
    void publishFrame(marcoSeleccionado);
  };


  /** El marco se dibuja arrastrando; las tarjetas cuyo centro cae dentro pasan a ser hijas por id. */
  const createFrameFromRect = useCallback((rect: FrameRect, toolId: string) => {
    const tool = getBoardTool(toolId);
    if (!tool || !activeBoard) return;
    const frame = tool.crear(rect.x, rect.y) as BoardCard;
    // Entropía pinta copias de las fuentes, no adopta las tarjetas que queden debajo.
    const children = esMarcoEntropia(frame) ? [] : cardsInsideFrame(activeBoard.cards, rect, measureCardSizes());
    const data = readFrameData(frame);
    frame.width = Math.max(FRAME_MIN_SIZE, rect.width);
    frame.datos = {
      ...frame.datos,
      ...data,
      alto: Math.max(FRAME_MIN_SIZE, rect.height),
      hijos: children,
      vista: 'libre',
    };
    updateBoard((board) => ({ ...board, cards: [...board.cards, frame] }));
    setSelectedCardIds([frame.id]);
    setFrameToolId(null);
    setFrameDraft(null);
    setNotice(children.length === 0
      ? 'Marco creado. No quedó ninguna tarjeta dentro.'
      : `Marco creado con ${children.length} ${children.length === 1 ? 'tarjeta' : 'tarjetas'} dentro.`);
  }, [activeBoard, measureCardSizes, updateBoard]);

  const handleWheel = useCallback((event: WheelEvent) => {
    event.preventDefault();
    detenerInercia();
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    // El gesto anula transiciones CSS de transform mientras dura; el DOM, no React.
    marcarGestoVisual(160);
    const actual = cameraRef.current;
    const delta = deltaDeRueda(event, rect.height);
    if (event.metaKey || event.ctrlKey) {
      const focal = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      // 1:1 con el delta del trackpad: sin muelle, sin lerp y sin inercia propia.
      cameraRef.current = zoomAtPoint(actual, actual.zoom * factorDePellizco(delta.y), focal);
    } else {
      cameraRef.current = { ...actual, pan: { x: actual.pan.x - delta.x, y: actual.pan.y - delta.y } };
    }
    // Se escribe en el transform en el mismo frame; rAF solo se usa para el arrastre.
    aplicarCamara();
    programarSincronizacion();
  }, [aplicarCamara, detenerInercia, marcarGestoVisual, programarSincronizacion]);

  useEffect(() => {
    wheelHandlerRef.current = handleWheel;
  }, [handleWheel]);

  // Se engancha una sola vez al viewport: cambiar de estado no deja una ventana sin rueda.
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const alRodar = (event: WheelEvent) => wheelHandlerRef.current(event);
    element.addEventListener('wheel', alRodar, { passive: false });
    return () => element.removeEventListener('wheel', alRodar);
  }, [loaded]);

  /**
   * Safari y WKWebView no siempre entregan el pellizco como ctrl+wheel. Los eventos
   * `gesture*` se cancelan para que el WebView no haga zoom de página y se traducen
   * al mismo zoom de cámara, sin muelle y en el mismo frame.
   */
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    let base: { zoom: number; pan: { x: number; y: number }; focal: { x: number; y: number } } | null = null;
    const start = (event: Event) => {
      const gesto = event as GestoWebKit;
      if (typeof gesto.scale !== 'number') return;
      event.preventDefault();
      detenerInercia();
      marcarGestoVisual();
      const rect = element.getBoundingClientRect();
      const focal = { x: (gesto.clientX ?? rect.left + rect.width / 2) - rect.left, y: (gesto.clientY ?? rect.top + rect.height / 2) - rect.top };
      base = { zoom: cameraRef.current.zoom, pan: cameraRef.current.pan, focal };
    };
    const change = (event: Event) => {
      const gesto = event as GestoWebKit;
      if (!base || typeof gesto.scale !== 'number') return;
      event.preventDefault();
      cameraRef.current = zoomAtPoint({ zoom: base.zoom, pan: base.pan }, base.zoom * gesto.scale, base.focal);
      aplicarCamara();
    };
    const end = (event: Event) => {
      if (!base) return;
      event.preventDefault();
      base = null;
      terminarGestoVisual();
      programarSincronizacion();
    };
    element.addEventListener('gesturestart', start, { passive: false });
    element.addEventListener('gesturechange', change, { passive: false });
    element.addEventListener('gestureend', end, { passive: false });
    return () => {
      element.removeEventListener('gesturestart', start);
      element.removeEventListener('gesturechange', change);
      element.removeEventListener('gestureend', end);
    };
  }, [aplicarCamara, detenerInercia, loaded, marcarGestoVisual, programarSincronizacion, terminarGestoVisual]);

  const zoomBy = (factor: number) => {
    const { width, height } = viewportSize;
    const camera = zoomAtPoint(cameraRef.current, cameraRef.current.zoom * factor, { x: width / 2, y: height / 2 });
    cameraRef.current = camera;
    aplicarCamara();
    sincronizarCamara();
  };

  const zoomTo = (value: number) => {
    const { width, height } = viewportSize;
    cameraRef.current = zoomAtPoint(cameraRef.current, value, { x: width / 2, y: height / 2 });
    aplicarCamara();
    sincronizarCamara();
  };

  /** ⇧2 · encuadra solo la selección, con el mismo techo de 800 %. */
  const fitSelection = useCallback(() => {
    if (!selectedCards.length || !viewportSize.width || !viewportSize.height) {
      setNotice('Selecciona al menos una tarjeta para ajustar el zoom a la selección.');
      return;
    }
    const sizes = measureCardSizes();
    const cajas = selectedCards.map((card) => rectDeTarjeta(card, sizes.get(card.id)));
    const minX = Math.min(...cajas.map((caja) => caja.x));
    const minY = Math.min(...cajas.map((caja) => caja.y));
    const maxX = Math.max(...cajas.map((caja) => caja.x + caja.width));
    const maxY = Math.max(...cajas.map((caja) => caja.y + caja.height));
    const zoom = Math.max(0.25, Math.min(8, (viewportSize.width - 80) / Math.max(1, maxX - minX), (viewportSize.height - 100) / Math.max(1, maxY - minY)));
    cameraRef.current = {
      zoom,
      pan: {
        x: viewportSize.width / 2 - ((minX + maxX) / 2) * zoom,
        y: viewportSize.height / 2 - ((minY + maxY) / 2) * zoom,
      },
    };
    aplicarCamara();
    sincronizarCamara();
  }, [aplicarCamara, measureCardSizes, selectedCards, sincronizarCamara, viewportSize.height, viewportSize.width]);

  const fitBoard = () => centerCamera(activeBoard);

  const iniciarMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    detenerInercia();
    marcarGestoVisual();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const modo = event.altKey ? 'restar' : event.shiftKey ? 'sumar' : 'reemplazar';
    marqueeDrag.current = { pointerId: event.pointerId, startX: x, startY: y, captureEl: event.currentTarget, modo };
    setMarquee({ x, y, width: 0, height: 0 });
    setGuias({});
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moverMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = marqueeDrag.current;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!drag || !rect || drag.pointerId !== event.pointerId) return;
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setMarquee({
      x: Math.min(drag.startX, x),
      y: Math.min(drag.startY, y),
      width: Math.abs(x - drag.startX),
      height: Math.abs(y - drag.startY),
    });
  };

  const terminarMarquesina = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = marqueeDrag.current;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!drag || !rect || drag.pointerId !== event.pointerId) return;
    marqueeDrag.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const ancho = Math.abs(x - drag.startX);
    const alto = Math.abs(y - drag.startY);
    setMarquee(null);
    if (ancho < 5 && alto < 5) return;
    const a = screenToWorld({ x: Math.min(drag.startX, x), y: Math.min(drag.startY, y) }, cameraRef.current);
    const b = screenToWorld({ x: Math.max(drag.startX, x), y: Math.max(drag.startY, y) }, cameraRef.current);
    const dentro = (activeBoard?.cards ?? []).filter((card) => {
      if (framedChildIds.has(card.id)) return false;
      const caja = rectDeTarjeta(card);
      const centroX = caja.x + caja.width / 2;
      const centroY = caja.y + caja.height / 2;
      return centroX >= a.x && centroX <= b.x && centroY >= a.y && centroY <= b.y;
    }).map((card) => card.id);
    const modo = drag.modo;
    setSelectedCardIds((current) => aplicarMarquesina(current, dentro, modo));
    suppressViewportClick.current = true;
    window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    setNotice(modo === 'reemplazar'
      ? (dentro.length
        ? `${dentro.length} ${dentro.length === 1 ? 'tarjeta seleccionada' : 'tarjetas seleccionadas'} con el rectángulo.`
        : 'El rectángulo no tocó ninguna tarjeta.')
      : modo === 'sumar'
        ? `Rectángulo sumado: ${dentro.length} ${dentro.length === 1 ? 'tarjeta más' : 'tarjetas más'}.`
        : `Rectángulo restado: ${dentro.length} ${dentro.length === 1 ? 'tarjeta' : 'tarjetas'}.`);
  };

  const beginPan = (event: React.PointerEvent<HTMLDivElement>, force = false) => {
    if (event.button !== 0 || (!force && (event.target as HTMLElement).closest('.board-card, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty'))) return;
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    setSettlingIds([]);
    setGuias({});
    limpiarInclinacion();
    const posicion = cameraRef.current.pan;
    panDrag.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      panX: posicion.x,
      panY: posicion.y,
      samples: [{ t: performance.now(), x: posicion.x, y: posicion.y }],
      captureEl: event.currentTarget,
    };
    setIsPanning(true);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const movePan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = panDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const siguiente = { x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y };
    cameraRef.current = { ...cameraRef.current, pan: siguiente };
    drag.samples.push({ t: performance.now(), x: siguiente.x, y: siguiente.y });
    if (drag.samples.length > 10) drag.samples.shift();
    pintarCamara();
  };

  const endPan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = panDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const movido = Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 4;
    panDrag.current = null;
    setIsPanning(false);
    liberarPuntero(drag.captureEl, event.pointerId);
    if (movido) {
      // Un paneo no es un clic en el vacío: no debe borrar la selección actual.
      suppressViewportClick.current = true;
      window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    }
    const velocidad = velocidadDeMuestras(drag.samples, 90);
    terminarGestoVisual();
    programarSincronizacion();
    iniciarInercia(velocidad.x, velocidad.y);
  };

  const viewportWorldPoint = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
  };

  const puntoDePegado = () => {
    if (lastPointerWorld.current) return lastPointerWorld.current;
    return screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, cameraRef.current);
  };

  const distanciaEntreToques = (): number => {
    const puntos = [...touchPoints.current.values()];
    if (puntos.length < 2) return 0;
    return Math.hypot(puntos[1].x - puntos[0].x, puntos[1].y - puntos[0].y);
  };

  const medioDeToques = (): { x: number; y: number } => {
    const puntos = [...touchPoints.current.values()];
    if (!puntos.length) return { x: 0, y: 0 };
    const suma = puntos.reduce((total, punto) => ({ x: total.x + punto.x, y: total.y + punto.y }), { x: 0, y: 0 });
    return { x: suma.x / puntos.length, y: suma.y / puntos.length };
  };

  /** Un dedo dibuja marquesina; dos dedos panean y pellizcan hacia el punto medio. */
  const iniciarToque = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('.board-card, .board-column, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty')) return;
    event.preventDefault();
    touchPoints.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* puntero sintético */ }
    if (touchIgnore.current) return;

    const cantidad = touchPoints.current.size;
    if (cantidad >= 2) {
      // El segundo dedo cancela la marquesina: dos dedos son cámara, nunca selección.
      if (marqueeDrag.current) {
        liberarPuntero(marqueeDrag.current.captureEl, marqueeDrag.current.pointerId);
        marqueeDrag.current = null;
      }
      setMarquee(null);
      detenerInercia();
      marcarGestoVisual();
      touchGesture.current = {
        mode: 'camera',
        baseCamera: { pan: { ...cameraRef.current.pan }, zoom: cameraRef.current.zoom },
        baseDist: Math.max(1, distanciaEntreToques()),
        baseMid: medioDeToques(),
      };
      return;
    }

    if (cantidad === 1) {
      if (handMode || spaceHeld.current) {
        detenerInercia();
        marcarGestoVisual();
        touchGesture.current = {
          mode: 'camera',
          baseCamera: { pan: { ...cameraRef.current.pan }, zoom: cameraRef.current.zoom },
          baseMid: { x: event.clientX, y: event.clientY },
        };
        return;
      }
      touchGesture.current = { mode: 'marquee' };
      iniciarMarquesina(event);
    }
  };

  const moverToque = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!touchPoints.current.has(event.pointerId)) return;
    touchPoints.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const gesto = touchGesture.current;
    if (!gesto) return;
    if (gesto.mode === 'marquee') {
      moverMarquesina(event);
      return;
    }
    if (!gesto.baseCamera) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const cantidad = touchPoints.current.size;
    const medio = medioDeToques();
    if (cantidad >= 2 && gesto.baseDist) {
      // Paneo del punto medio + zoom focal en el mismo frame, sin inercia propia.
      const panned = {
        zoom: gesto.baseCamera.zoom,
        pan: {
          x: gesto.baseCamera.pan.x + (medio.x - (gesto.baseMid?.x ?? medio.x)),
          y: gesto.baseCamera.pan.y + (medio.y - (gesto.baseMid?.y ?? medio.y)),
        },
      };
      const escala = distanciaEntreToques() / gesto.baseDist;
      cameraRef.current = zoomAtPoint(panned, gesto.baseCamera.zoom * escala, { x: medio.x - rect.left, y: medio.y - rect.top });
    } else {
      cameraRef.current = {
        zoom: gesto.baseCamera.zoom,
        pan: {
          x: gesto.baseCamera.pan.x + (event.clientX - (gesto.baseMid?.x ?? event.clientX)),
          y: gesto.baseCamera.pan.y + (event.clientY - (gesto.baseMid?.y ?? event.clientY)),
        },
      };
    }
    aplicarCamara();
  };

  const terminarToque = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!touchPoints.current.has(event.pointerId)) return;
    touchPoints.current.delete(event.pointerId);
    const gesto = touchGesture.current;
    if (gesto?.mode === 'marquee' && marqueeDrag.current?.pointerId === event.pointerId) {
      terminarMarquesina(event);
    }
    if (touchPoints.current.size < 2 && gesto?.mode === 'camera') {
      touchGesture.current = null;
      // El dedo que queda no debe convertirse en marquesina sin levantar del todo.
      touchIgnore.current = touchPoints.current.size > 0;
      terminarGestoVisual();
      programarSincronizacion();
    }
    if (touchPoints.current.size === 0) {
      touchGesture.current = null;
      touchIgnore.current = false;
      terminarGestoVisual();
      programarSincronizacion();
    }
  };

  const startFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !frameToolId) return;
    if ((event.target as HTMLElement).closest('button, input, select, textarea, a, .board-free-media, .board-zoom-controls, .board-empty, .board-controls')) return;
    detenerInercia();
    marcarGestoVisual();
    const start = viewportWorldPoint(event);
    frameDraw.current = { pointerId: event.pointerId, start, captureEl: event.currentTarget };
    setFrameDraft(rectFromPoints(start, start));
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moveFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = frameDraw.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setFrameDraft(rectFromPoints(drag.start, viewportWorldPoint(event)));
  };

  const endFrameDraw = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = frameDraw.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const rect = rectFromPoints(drag.start, viewportWorldPoint(event));
    frameDraw.current = null;
    terminarGestoVisual();
    liberarPuntero(drag.captureEl, event.pointerId);
    suppressViewportClick.current = true;
    window.setTimeout(() => { suppressViewportClick.current = false; }, 0);
    if (!frameToolId) {
      setFrameDraft(null);
      return;
    }
    if (rect.width < FRAME_MIN_SIZE || rect.height < FRAME_MIN_SIZE) {
      setFrameDraft(null);
      setNotice(`El marco necesita al menos ${FRAME_MIN_SIZE} × ${FRAME_MIN_SIZE}. Vuelve a arrastrar o pulsa Escape.`);
      return;
    }
    createFrameFromRect(rect, frameToolId);
  };

  const beginViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (rect) lastPointerWorld.current = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    if (event.pointerType === 'touch') {
      iniciarToque(event);
      return;
    }
    const target = event.target as HTMLElement;
    if (!target.closest('input, textarea, select, [contenteditable="true"]')) {
      viewportRef.current?.focus({ preventScroll: true });
    }
    if (spaceHeld.current && event.button === 0) {
      beginPan(event, true);
      return;
    }
    if (frameToolId) {
      startFrameDraw(event);
      return;
    }
    if (handMode && event.button === 0) {
      beginPan(event);
      return;
    }
    if (event.button === 0) {
      const target = event.target as HTMLElement;
      if (!target.closest('.board-card, .board-column, .board-frame, .board-free-media, .board-controls, .board-dialog, button, input, select, a, .board-empty')) {
        iniciarMarquesina(event);
        return;
      }
    }
    beginPan(event);
  };

  const moveViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = viewportRef.current?.getBoundingClientRect();
    if (rect && event.pointerType !== 'touch') lastPointerWorld.current = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    if (event.pointerType === 'touch') {
      moverToque(event);
      return;
    }
    if (marqueeDrag.current) moverMarquesina(event);
    else if (frameDraw.current) moveFrameDraw(event);
    else movePan(event);
  };

  const endViewportGesture = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'touch') {
      terminarToque(event);
      return;
    }
    if (marqueeDrag.current) terminarMarquesina(event);
    else if (frameDraw.current) endFrameDraw(event);
    else endPan(event);
  };

  const startCardDrag = (card: BoardCard, event: React.PointerEvent<HTMLElement>, force = false) => {
    detenerInercia();
    const profundo = event.metaKey || event.ctrlKey;
    if (spaceHeld.current || event.button !== 0 || event.detail > 1 || frameToolId || connectMode || card.locked
      || (!force && (event.target as HTMLElement).closest('input,button,a,textarea,select,[contenteditable="true"],.board-inline-input'))
      || !activeBoard) return;
    marcarGestoVisual();
    suppressCardClick.current = false;
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    setSettlingIds([]);
    setGuias({});
    limpiarInclinacion();
    let nextSelection = selectedCardIds;
    if (profundo) {
      // ⌘/Ctrl + arrastrar toma lo que hay debajo (aunque estés editando o dentro de un marco).
      // El clic sin arrastre sigue alternando la selección.
    } else if (event.shiftKey) {
      nextSelection = alternarEnSeleccion(selectedCardIds, card.id);
      suppressCardClick.current = true;
    } else if (!selectedCardIds.includes(card.id)) {
      nextSelection = [card.id];
    }
    if (nextSelection !== selectedCardIds) setSelectedCardIds(nextSelection);
    if (event.shiftKey && !nextSelection.includes(card.id)) return;

    const idsBrutos = profundo || event.shiftKey
      ? [card.id]
      : card.type === 'marco'
        ? [...new Set([...nextSelection.includes(card.id) ? nextSelection : [card.id], ...readFrameData(card).hijos])]
        : card.type === 'columna'
          ? [...new Set([...nextSelection.includes(card.id) ? nextSelection : [card.id], ...readColumnData(card).hijos])]
          : nextSelection.includes(card.id) ? nextSelection : [card.id];
    // Una tarjeta bloqueada nunca entra en un arrastre múltiple.
    const ids = idsBrutos.filter((id) => !activeBoard.cards.find((item) => item.id === id)?.locked);
    const positions = new Map(
      activeBoard.cards.filter((item) => ids.includes(item.id)).map((item) => [item.id, { x: item.x, y: item.y }]),
    );
    // Solo se mide la tarjeta que se agarra. Medir las 500 en el pointerdown
    // convertía un clic en una tarea de 200 ms; las demás usan su ancho guardado
    // y un alto razonable para el imán.
    const sizes = new Map<string, CardSize>();
    const elementoAgarrado = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`);
    const cajaAgarrada = elementoAgarrado?.getBoundingClientRect();
    sizes.set(card.id, {
      width: card.width,
      height: card.type === 'marco' ? readFrameData(card).alto : cajaAgarrada ? cajaAgarrada.height / cameraRef.current.zoom : 200,
    });
    cardDrag.current = {
      pointerId: event.pointerId,
      boardId: activeBoard.id,
      ids,
      x: event.clientX,
      y: event.clientY,
      positions,
      sizes,
      startBoard: activeBoard,
      gesture: newBoardId('move'),
      moved: false,
      captureEl: event.currentTarget,
      lastX: event.clientX,
      lastY: event.clientY,
      lastT: performance.now(),
      altKey: event.altKey,
      duplicated: false,
    };
    setDraggingIds(ids);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
  };

  const moveCardDrag = (event: React.PointerEvent<HTMLElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const distancia = Math.max(Math.abs(event.clientX - drag.x), Math.abs(event.clientY - drag.y));
    if (!drag.moved && distancia < 4) return;
    if (!drag.moved) {
      drag.moved = true;
      try { drag.captureEl?.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
    }
    // Alt/Opción + arrastrar: la copia nace en el primer movimiento, no al hacer clic.
    let base: BoardDocument = boards.find((board) => board.id === drag.boardId) ?? activeBoard;
    if (!base) return;
    if (drag.altKey && !drag.duplicated) {
      const dup = duplicateCards(base.cards, base.relations, drag.ids, { x: 0, y: 0 });
      const sizes = new Map<string, CardSize>();
      for (const [viejo, nuevo] of dup.idMap) {
        const medida = drag.sizes.get(viejo);
        if (medida) sizes.set(nuevo, medida);
      }
      base = {
        ...base,
        updatedAt: new Date().toISOString(),
        cards: [...base.cards, ...dup.cards],
        relations: [...base.relations, ...dup.relations],
      };
      drag.ids = dup.newIds;
      drag.positions = new Map(dup.cards.map((item) => [item.id, { x: item.x, y: item.y }]));
      drag.sizes = sizes;
      drag.duplicated = true;
      setSelectedCardIds(dup.newIds);
      setNotice(`Copia creada: ${dup.newIds.length === 1 ? '1 tarjeta' : `${dup.newIds.length} tarjetas`}.`);
    }
    let deltaX = (event.clientX - drag.x) / cameraRef.current.zoom;
    let deltaY = (event.clientY - drag.y) / cameraRef.current.zoom;
    const anchor = drag.positions.get(drag.ids[0]);
    if (snapEnabled && anchor) {
      deltaX = snapPosition(anchor.x + deltaX, GRID_SIZE) - anchor.x;
      deltaY = snapPosition(anchor.y + deltaY, GRID_SIZE) - anchor.y;
    }
    const tablero = base;
    const arrastrados = new Set(drag.ids);
    if (anchor && tablero) {
      const tamano = drag.sizes.get(drag.ids[0]) ?? { width: 260, height: 200 };
      const caja = { x: anchor.x + deltaX, y: anchor.y + deltaY, width: tamano.width, height: tamano.height };
      const otras = tablero.cards
        .filter((item) => !arrastrados.has(item.id))
        .map((item) => {
          const medida = drag.sizes.get(item.id);
          return {
            x: item.x,
            y: item.y,
            width: medida?.width ?? item.width,
            height: medida?.height ?? (item.type === 'marco' ? readFrameData(item).alto : 200),
          };
        });
      // La retícula ya se aplicó arriba; aquí el imán solo compara con otras tarjetas.
      const iman = snapEnabled
        ? imanDeCaja(caja, otras, { umbral: 7 / Math.max(0.05, cameraRef.current.zoom), rejilla: 0 })
        : { dx: 0, dy: 0, guias: {} as GuiasIman };
      deltaX += iman.dx;
      deltaY += iman.dy;
      setGuias((actual) => actual.x === iman.guias.x && actual.y === iman.guias.y ? actual : iman.guias);
    } else {
      setGuias((actual) => actual.x === undefined && actual.y === undefined ? actual : {});
    }
    if (deltaX !== 0 || deltaY !== 0) drag.moved = true;

    const ahora = performance.now();
    const dt = Math.max(1, ahora - drag.lastT);
    const vx = ((event.clientX - drag.lastX) / dt) * 1000;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    drag.lastT = ahora;
    if (!movimientoReducido()) {
      viewportRef.current?.style.setProperty('--drag-tilt', `${inclinacionPorVelocidad(vx)}deg`);
    }

    updateBoard(() => ({
      ...tablero,
      cards: tablero.cards.map((item) => {
        const position = drag.positions.get(item.id);
        return position ? { ...item, x: position.x + deltaX, y: position.y + deltaY } : item;
      }),
    }), { recordHistory: false });

    const esMarcoArrastrado = drag.ids.some((id) => {
      const tipo = tablero?.cards.find((item) => item.id === id)?.type;
      return tipo === 'marco' || tipo === 'columna';
    });
    if (!tablero || esMarcoArrastrado) {
      setDropFrameId(null);
      dropFrameIdRef.current = null;
      return;
    }
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    const destino = tablero.cards.find((item) => {
      if (arrastrados.has(item.id)) return false;
      if (item.type !== 'marco' && item.type !== 'columna') return false;
      const alto = item.type === 'columna'
        ? (viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${item.id}"]`)?.getBoundingClientRect().height ?? 200) / cameraRef.current.zoom
        : readFrameData(item).alto;
      return punto.x >= item.x && punto.x <= item.x + item.width && punto.y >= item.y && punto.y <= item.y + alto;
    });
    const siguienteDestino = destino?.id ?? null;
    dropFrameIdRef.current = siguienteDestino;
    setDropFrameId((actual) => actual === siguienteDestino ? actual : siguienteDestino);
  };

  const asentar = (ids: string[]) => {
    if (movimientoReducido() || !ids.length) {
      limpiarInclinacion();
      return;
    }
    setSettlingIds(ids);
    if (settleTimer.current) window.clearTimeout(settleTimer.current);
    settleTimer.current = window.setTimeout(() => {
      settleTimer.current = null;
      setSettlingIds([]);
      limpiarInclinacion();
    }, 280);
  };

  const endCardDrag = (event: React.PointerEvent<HTMLElement>) => {
    const drag = cardDrag.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const tablero = boards.find((board) => board.id === drag.boardId) ?? activeBoard;
    const destino = dropFrameIdRef.current;
    let final = tablero;
    const arrastraContenedor = Boolean(tablero && drag.ids.some((id) => {
      const tipo = tablero.cards.find((item) => item.id === id)?.type;
      return tipo === 'marco' || tipo === 'columna';
    }));
    if (tablero && !arrastraContenedor) {
      const adoptados = new Set(drag.ids);
      final = {
        ...tablero,
        updatedAt: new Date().toISOString(),
        cards: tablero.cards.map((item) => {
          if (item.type === 'columna') {
            const datos = readColumnData(item);
            const hijos = datos.hijos.filter((id) => !adoptados.has(id));
            return destino === item.id
              ? { ...item, datos: { ...item.datos, ...datos, hijos: [...new Set([...hijos, ...drag.ids])], ordenExplicito: true } }
              : { ...item, datos: { ...item.datos, ...datos, hijos } };
          }
          if (item.type !== 'marco') return item;
          const datos = readFrameData(item);
          const hijos = datos.hijos.filter((id) => !adoptados.has(id));
          return destino === item.id
            ? { ...item, datos: { ...item.datos, ...datos, hijos: [...new Set([...hijos, ...drag.ids])] } }
            : { ...item, datos: { ...item.datos, ...datos, hijos } };
        }),
      };
    }
    if (final && drag.ids.some((id) => {
      const before = drag.startBoard.cards.find((item) => item.id === id);
      const after = final.cards.find((item) => item.id === id);
      return before && after && (before.x !== after.x || before.y !== after.y);
    })) {
      setBoardHistories((current) => ({
        ...current,
        [drag.boardId]: recordBoardChange(current[drag.boardId] ?? emptyBoardHistory(), drag.startBoard, final, drag.gesture),
      }));
    }
    if (final && final !== tablero) {
      setBoards((current) => current.map((board) => board.id === final.id ? final : board));
      enqueueBoardSave(final);
    }
    if (drag.moved || destino) suppressCardClick.current = true;
    liberarPuntero(drag.captureEl, drag.pointerId);
    setDraggingIds([]);
    setDropFrameId(null);
    dropFrameIdRef.current = null;
    setGuias({});
    if (drag.moved) asentar(drag.ids);
    else limpiarInclinacion();
    cardDrag.current = null;
    terminarGestoVisual();
  };

  /** H6 · asas de 4 bordes y 4 esquinas para marcos y columnas. */
  const startFrameResize = (card: BoardCard, direction: string, event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0 || !activeBoard || card.locked) return;
    event.preventDefault();
    event.stopPropagation();
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`) ?? null;
    const alto = card.type === 'marco'
      ? readFrameData(card).alto
      : readColumnData(card).alto ?? (elemento ? elemento.getBoundingClientRect().height / cameraRef.current.zoom : 300);
    frameResize.current = {
      pointerId: event.pointerId,
      cardId: card.id,
      tipo: card.type === 'columna' ? 'columna' : 'marco',
      dir: direction,
      startX: event.clientX,
      startY: event.clientY,
      x: card.x,
      y: card.y,
      width: card.width,
      height: alto,
      startBoard: activeBoard,
      captureEl: event.currentTarget,
      elemento,
      raf: 0,
      ultimo: { x: card.x, y: card.y, width: card.width, height: alto },
    };
    setDraggingIds([card.id]);
    setSettlingIds([]);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moveFrameResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = frameResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const escala = cameraRef.current.zoom;
    const dx = (event.clientX - drag.startX) / escala;
    const dy = (event.clientY - drag.startY) / escala;
    const minimo = drag.tipo === 'marco' ? FRAME_MIN_SIZE : COLUMN_MIN_HEIGHT;
    let ancho = drag.width + (drag.dir.includes('e') ? dx : 0) - (drag.dir.includes('w') ? dx : 0);
    let alto = drag.height + (drag.dir.includes('s') ? dy : 0) - (drag.dir.includes('n') ? dy : 0);
    ancho = Math.max(minimo, ancho);
    alto = Math.max(minimo, alto);
    const x = drag.dir.includes('w') ? drag.x + (drag.width - ancho) : drag.x;
    const y = drag.dir.includes('n') ? drag.y + (drag.height - alto) : drag.y;
    drag.ultimo = {
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      width: Math.round(ancho * 10) / 10,
      height: Math.round(alto * 10) / 10,
    };
    // Ref + rAF: durante el gesto solo cambia el DOM; React recibe el tamaño al soltar.
    if (drag.raf) return;
    drag.raf = requestAnimationFrame(() => {
      drag.raf = 0;
      if (frameResize.current !== drag || !drag.elemento) return;
      drag.elemento.style.left = `${drag.ultimo.x}px`;
      drag.elemento.style.top = `${drag.ultimo.y}px`;
      drag.elemento.style.width = `${drag.ultimo.width}px`;
      drag.elemento.style.height = `${drag.ultimo.height}px`;
    });
  };

  const endFrameResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = frameResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.raf) {
      cancelAnimationFrame(drag.raf);
      drag.raf = 0;
    }
    frameResize.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    terminarGestoVisual();
    setDraggingIds([]);
    const tablero = boards.find((board) => board.id === drag.startBoard.id) ?? activeBoard;
    const card = tablero?.cards.find((item) => item.id === drag.cardId);
    if (!tablero || !card) return;
    const { x, y, width, height } = drag.ultimo;
    let final: BoardDocument;
    if (drag.tipo === 'marco') {
      const datos = readFrameData(card);
      const rect: FrameRect = { x, y, width, height };
      const hijos = esMarcoEntropia(card)
        ? datos.hijos
        : cardsInsideFrame(tablero.cards, rect, measureCardSizes()).filter((id) => id !== card.id);
      final = {
        ...tablero,
        updatedAt: new Date().toISOString(),
        cards: tablero.cards.map((item) => item.id === card.id
          ? { ...item, x, y, width, datos: { ...item.datos, ...datos, alto: height, hijos } }
          : item),
      };
    } else {
      const datos = readColumnData(card);
      final = {
        ...tablero,
        updatedAt: new Date().toISOString(),
        cards: tablero.cards.map((item) => item.id === card.id
          ? { ...item, x, y, width, datos: { ...item.datos, ...datos, alto: height } }
          : item),
      };
    }
    setBoardHistories((current) => ({
      ...current,
      [drag.startBoard.id]: recordBoardChange(current[drag.startBoard.id] ?? emptyBoardHistory(), drag.startBoard, final, newBoardId('resize')),
    }));
    setBoards((current) => current.map((board) => board.id === final.id ? final : board));
    enqueueBoardSave(final);
    asentar([card.id]);
  };

  /** H6 · asa de ancho de una nota (o de toda la selección). El alto sigue al contenido. */
  const startWidthResize = useCallback((card: BoardCard, event: React.PointerEvent<HTMLElement>) => {
    const board = activeBoardRef.current;
    if (event.button !== 0 || !board || card.locked) return;
    event.preventDefault();
    event.stopPropagation();
    detenerInercia();
    marcarGestoVisual();
    const seleccionActual = selectedIdsRef.current;
    const seleccion = seleccionActual.includes(card.id) ? seleccionActual : [card.id];
    const ids = seleccion.filter((id) => {
      const item = board.cards.find((candidate) => candidate.id === id);
      return Boolean(item && !item.locked && item.type !== 'marco' && item.type !== 'media');
    });
    if (!ids.includes(card.id)) ids.push(card.id);
    const startWidths = new Map(ids.map((id) => [id, board.cards.find((item) => item.id === id)?.width ?? card.width]));
    widthResize.current = {
      pointerId: event.pointerId,
      ids,
      startX: event.clientX,
      startWidths,
      startBoard: board,
      captureEl: event.currentTarget,
      raf: 0,
      ultimas: new Map(startWidths),
    };
    setSettlingIds([]);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  }, [detenerInercia, marcarGestoVisual]);

  const moveWidthResize = useCallback((event: React.PointerEvent<HTMLElement>) => {
    const drag = widthResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const delta = (event.clientX - drag.startX) / cameraRef.current.zoom;
    for (const [id, inicial] of drag.startWidths) {
      const limite = 640;
      drag.ultimas.set(id, Math.round(Math.max(210, Math.min(limite, inicial + delta)) * 10) / 10);
    }
    if (drag.raf) return;
    drag.raf = requestAnimationFrame(() => {
      drag.raf = 0;
      if (widthResize.current !== drag) return;
      for (const [id, ancho] of drag.ultimas) {
        const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${id}"]`);
        if (elemento) elemento.style.width = `${ancho}px`;
      }
    });
  }, []);

  const endWidthResize = useCallback((event: React.PointerEvent<HTMLElement>) => {
    const drag = widthResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.raf) { cancelAnimationFrame(drag.raf); drag.raf = 0; }
    widthResize.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    terminarGestoVisual();
    const tablero = boardsRef.current.find((board) => board.id === drag.startBoard.id) ?? activeBoardRef.current;
    if (!tablero) return;
    const final: BoardDocument = {
      ...tablero,
      updatedAt: new Date().toISOString(),
      cards: tablero.cards.map((item) => drag.ultimas.has(item.id)
        ? { ...item, width: Math.max(210, Math.min(640, drag.ultimas.get(item.id)!)) }
        : item),
    };
    setBoardHistories((current) => ({
      ...current,
      [drag.startBoard.id]: recordBoardChange(current[drag.startBoard.id] ?? emptyBoardHistory(), drag.startBoard, final, newBoardId('resize-ancho')),
    }));
    setBoards((current) => current.map((board) => board.id === final.id ? final : board));
    enqueueBoardSave(final);
  }, [terminarGestoVisual]);

  /** Redimensionar una imagen o vídeo desde cualquier esquina; Shift mantiene la proporción. */
  const startFreeResize = (card: BoardCard, corner: EsquinaMedia, event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0 || !activeBoard) return;
    event.preventDefault();
    event.stopPropagation();
    detenerInercia();
    marcarGestoVisual();
    if (settleTimer.current) { window.clearTimeout(settleTimer.current); settleTimer.current = null; }
    const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`) ?? null;
    const alto = card.height ?? (elemento ? elemento.getBoundingClientRect().height / cameraRef.current.zoom : Math.round(card.width * 0.75));
    freeResize.current = {
      pointerId: event.pointerId,
      cardId: card.id,
      corner,
      startX: event.clientX,
      startY: event.clientY,
      x: card.x,
      y: card.y,
      width: card.width,
      height: alto,
      ratio: card.width / Math.max(1, alto),
      startBoard: activeBoard,
      captureEl: event.currentTarget,
      elemento,
      raf: 0,
      ultimo: { x: card.x, y: card.y, width: card.width, height: alto },
    };
    setSelectedCardIds([card.id]);
    setSettlingIds([]);
    try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* el puntero ya se soltó */ }
  };

  const moveFreeResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = freeResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const escala = cameraRef.current.zoom;
    const dx = (event.clientX - drag.startX) / escala;
    const dy = (event.clientY - drag.startY) / escala;
    const oeste = drag.corner === 'nw' || drag.corner === 'sw';
    const norte = drag.corner === 'nw' || drag.corner === 'ne';
    const brutoAncho = oeste ? drag.width - dx : drag.width + dx;
    const brutoAlto = norte ? drag.height - dy : drag.height + dy;
    let ancho = Math.max(80, brutoAncho);
    let alto = Math.max(60, brutoAlto);
    // Shift = proporción. Sin Shift, la esquina sigue al dedo en ambos ejes.
    if (event.shiftKey) {
      const mandaAncho = Math.abs(brutoAncho - drag.width) >= Math.abs(brutoAlto - drag.height);
      if (mandaAncho) {
        ancho = Math.max(80, brutoAncho);
        alto = ancho / drag.ratio;
        if (alto < 60) { alto = 60; ancho = alto * drag.ratio; }
      } else {
        alto = Math.max(60, brutoAlto);
        ancho = alto * drag.ratio;
        if (ancho < 80) { ancho = 80; alto = ancho / drag.ratio; }
      }
    }
    const x = oeste ? drag.x + (drag.width - ancho) : drag.x;
    const y = norte ? drag.y + (drag.height - alto) : drag.y;
    drag.ultimo = {
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      width: Math.round(ancho * 10) / 10,
      height: Math.round(alto * 10) / 10,
    };
    // Ref + rAF: durante el gesto solo cambia el DOM; React recibe el tamaño al soltar.
    if (drag.raf) return;
    drag.raf = requestAnimationFrame(() => {
      drag.raf = 0;
      if (freeResize.current !== drag || !drag.elemento || !drag.ultimo) return;
      const { x: left, y: top, width, height } = drag.ultimo;
      drag.elemento.style.left = `${left}px`;
      drag.elemento.style.top = `${top}px`;
      drag.elemento.style.width = `${width}px`;
      drag.elemento.style.height = `${height}px`;
    });
  };

  const endFreeResize = (event: React.PointerEvent<HTMLElement>) => {
    const drag = freeResize.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.raf) {
      cancelAnimationFrame(drag.raf);
      drag.raf = 0;
    }
    freeResize.current = null;
    liberarPuntero(drag.captureEl, event.pointerId);
    terminarGestoVisual();
    const tablero = boards.find((board) => board.id === drag.startBoard.id) ?? activeBoard;
    const card = tablero?.cards.find((item) => item.id === drag.cardId);
    if (!tablero || !card) return;
    const tamano = drag.ultimo;
    if (!tamano) return;
    const final: BoardDocument = {
      ...tablero,
      updatedAt: new Date().toISOString(),
      cards: tablero.cards.map((item) => item.id === drag.cardId
        ? { ...item, x: tamano.x, y: tamano.y, width: tamano.width, height: tamano.height }
        : item),
    };
    setBoardHistories((current) => ({
      ...current,
      [drag.startBoard.id]: recordBoardChange(current[drag.startBoard.id] ?? emptyBoardHistory(), drag.startBoard, final, newBoardId('resize-media')),
    }));
    setBoards((current) => current.map((board) => board.id === final.id ? final : board));
    enqueueBoardSave(final);
  };

  const ajustarAlturaNatural = useCallback((cardId: string, anchoNatural: number, altoNatural: number) => {
    if (!anchoNatural || !altoNatural) return;
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((item) => item.id === cardId && item.height === undefined
        ? { ...item, height: Math.round(item.width * (altoNatural / anchoNatural) * 10) / 10 }
        : item),
    }), { recordHistory: false });
  }, [updateBoard]);

  const alignSelection = (alignment: Alignment) => {
    if (selectedCardIds.length < 2) return;
    const sizes = measureCardSizes();
    updateBoard((board) => ({
      ...board,
      cards: alignCards(board.cards, selectedCardIds, alignment, sizes),
    }));
  };

  const distributeSelection = (axis: DistributionAxis) => {
    if (selectedCardIds.length < 3) return;
    const sizes = measureCardSizes();
    updateBoard((board) => ({
      ...board,
      cards: distributeCards(board.cards, selectedCardIds, axis, sizes),
    }));
  };

  /** ⌘G · un marco nuevo alrededor de la selección, detrás de sus hijos y sin mover nada. */
  const agruparSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board) return;
    const ids = selectedCardIds.filter((id) => {
      const card = board.cards.find((item) => item.id === id);
      return Boolean(card && card.type !== 'marco' && !card.locked);
    });
    if (!ids.length) {
      setNotice('Selecciona al menos una tarjeta libre para agruparla en un marco.');
      return;
    }
    const sizes = measureCardSizes();
    const cajas = board.cards
      .filter((card) => ids.includes(card.id))
      .map((card) => rectDeTarjeta(card, sizes.get(card.id)));
    const izquierda = Math.min(...cajas.map((caja) => caja.x));
    const arriba = Math.min(...cajas.map((caja) => caja.y));
    const derecha = Math.max(...cajas.map((caja) => caja.x + caja.width));
    const abajo = Math.max(...cajas.map((caja) => caja.y + caja.height));
    const margen = 32;
    const frame = getBoardTool('marco')?.crear(izquierda - margen, arriba - margen) as BoardCard | undefined;
    if (!frame) return;
    const data = readFrameData(frame);
    const ancho = Math.max(FRAME_MIN_SIZE, derecha - izquierda + margen * 2);
    const alto = Math.max(FRAME_MIN_SIZE, abajo - arriba + margen * 2);
    const conHijos: BoardCard = {
      ...frame,
      title: 'Grupo',
      width: ancho,
      datos: { ...frame.datos, ...data, alto, hijos: ids, vista: 'libre' },
    };
    updateBoard((actual) => {
      const primero = Math.min(...ids.map((id) => actual.cards.findIndex((card) => card.id === id)));
      const indice = primero < 0 ? actual.cards.length : primero;
      return {
        ...actual,
        cards: [...actual.cards.slice(0, indice), conHijos, ...actual.cards.slice(indice)],
      };
    });
    setSelectedCardIds([conHijos.id]);
    setNotice(`Grupo creado con ${ids.length} ${ids.length === 1 ? 'tarjeta' : 'tarjetas'}.`);
  }, [measureCardSizes, selectedCardIds, updateBoard]);

  /** ⌘⇧G · quita el marco (o saca las tarjetas seleccionadas) sin tocar posiciones. */
  const desagruparSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const seleccionadas = new Set(selectedCardIds);
    const marcos = board.cards.filter((card) => seleccionadas.has(card.id) && card.type === 'marco');
    const sueltas = board.cards.filter((card) => seleccionadas.has(card.id) && card.type !== 'marco');
    if (!marcos.length && !sueltas.length) return;
    const quitar = new Set([...marcos.map((card) => card.id), ...sueltas.map((card) => card.id)]);
    updateBoard((actual) => ({
      ...actual,
      cards: actual.cards
        .filter((card) => !marcos.some((marco) => marco.id === card.id))
        .map((card) => {
          if (card.type !== 'marco' && card.type !== 'columna') return card;
          const data = card.type === 'marco' ? readFrameData(card) : readColumnData(card);
          const hijos = data.hijos.filter((id) => !quitar.has(id));
          return hijos.length === data.hijos.length
            ? card
            : { ...card, datos: { ...card.datos, ...data, hijos } };
        }),
    }));
    setSelectedCardIds((current) => current.filter((id) => !marcos.some((marco) => marco.id === id)));
    setNotice(marcos.length
      ? `${marcos.length} ${marcos.length === 1 ? 'marco desagrupado' : 'marcos desagrupados'} sin mover ninguna tarjeta.`
      : `${sueltas.length} ${sueltas.length === 1 ? 'tarjeta liberada' : 'tarjetas liberadas'} del marco.`);
  }, [selectedCardIds, updateBoard]);

  const mostrarAviso = useCallback((texto: string, deshacer?: () => void, historial = false) => {
    if (avisoTimer.current) window.clearTimeout(avisoTimer.current);
    setAviso({ texto, deshacer, historial });
    avisoTimer.current = window.setTimeout(() => {
      avisoTimer.current = null;
      setAviso(null);
    }, 5000);
  }, []);

  useEffect(() => () => {
    if (avisoTimer.current) window.clearTimeout(avisoTimer.current);
  }, []);

  const undo = useCallback(() => {
    if (!activeBoard) return;
    const history = boardHistories[activeBoard.id] ?? emptyBoardHistory();
    const result = undoBoardChange(history, activeBoard);
    if (!result.board) return;
    setBoardHistories((current) => ({ ...current, [activeBoard.id]: result.history }));
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? result.board! : board));
    setSelectedCardIds((current) => current.filter((id) => result.board!.cards.some((card) => card.id === id)));
    setAviso((current) => current?.historial ? null : current);
    enqueueBoardSave(result.board!);
  }, [activeBoard, boardHistories]);

  const redo = useCallback(() => {
    if (!activeBoard) return;
    const history = boardHistories[activeBoard.id] ?? emptyBoardHistory();
    const result = redoBoardChange(history, activeBoard);
    if (!result.board) return;
    setBoardHistories((current) => ({ ...current, [activeBoard.id]: result.history }));
    setBoards((current) => current.map((board) => board.id === activeBoard.id ? result.board! : board));
    setSelectedCardIds((current) => current.filter((id) => result.board!.cards.some((card) => card.id === id)));
    setAviso((current) => current?.historial ? null : current);
    enqueueBoardSave(result.board!);
  }, [activeBoard, boardHistories]);

  // Un solo listener de teclado para todo el lienzo. La tabla de atajos decide
  // qué hacer; aquí solo se filtran el foco y la repetición.
  useEffect(() => {
    const setSpace = (held: boolean) => {
      spaceHeld.current = held;
      setSpacePanActive(held);
    };
    const down = (event: KeyboardEvent) => {
      if (locked) return;
      // H4 · Alt+flecha va al vecino geométrico, no mueve la tarjeta.
      if (event.altKey && !event.metaKey && !event.ctrlKey && event.key.startsWith('Arrow') && !esObjetivoDeTexto(event.target)) {
        if (document.querySelector('[role="dialog"], [role="alertdialog"]')) return;
        const tablero = activeBoardRef.current;
        if (!tablero?.cards.length) return;
        const direccion: Direccion = event.key === 'ArrowLeft' ? 'izquierda'
          : event.key === 'ArrowRight' ? 'derecha'
            : event.key === 'ArrowUp' ? 'arriba' : 'abajo';
        const enfocado = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('[data-card-id]')?.dataset.cardId ?? null;
        const siguiente = enfocado ? vecinoGeometrico(tablero.cards, enfocado, direccion) : tablero.cards[0].id;
        if (siguiente) {
          const elemento = viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${CSS.escape(siguiente)}"]`);
          if (elemento) {
            event.preventDefault();
            elemento.focus();
          }
        }
        return;
      }
      const atajo = atajoParaEvento(event);
      if (!atajo) return;
      if (event.repeat && !atajo.repetible) return;
      // Esc sigue cerrando diálogos aunque el foco esté en un campo; el resto no.
      if (atajo.accion !== 'cerrar' && esObjetivoDeTexto(event.target)) return;
      ejecutarAtajoRef.current(atajo, event);
    };
    const up = (event: KeyboardEvent) => {
      if (event.code !== 'Space') return;
      if (spaceHeld.current) event.preventDefault();
      setSpace(false);
    };
    const blur = () => setSpace(false);
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', blur);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', blur);
    };
  }, [locked]);

  useEffect(() => {
    if (!exportMenuOpen && !libraryMenuOpen && !projectMenuOpen) return;
    const cerrar = (event: PointerEvent) => {
      const target = event.target as Node;
      if (exportMenuRef.current?.contains(target) || libraryMenuRef.current?.contains(target) || projectMenuRef.current?.contains(target)) return;
      setExportMenuOpen(false);
      setLibraryMenuOpen(false);
      setProjectMenuOpen(false);
    };
    window.addEventListener('pointerdown', cerrar);
    return () => window.removeEventListener('pointerdown', cerrar);
  }, [exportMenuOpen, libraryMenuOpen, projectMenuOpen]);

  const handleCardSelection = (cardId: string, event: Modificadores) => {
    if (spaceHeld.current) return;
    if (suppressCardClick.current) {
      suppressCardClick.current = false;
      return;
    }
    if (event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, cardId));
    } else if (event.shiftKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, cardId));
    } else {
      setSelectedCardIds([cardId]);
    }
  };

  /** El engranaje edita la tarjeta pulsada y, si hay varias seleccionadas, todas. */
  const abrirAjustesTarjeta = useCallback((card: BoardCard, event: React.MouseEvent<HTMLElement>) => {
    const actuales = selectedIdsRef.current;
    const ids = actuales.includes(card.id) ? actuales : [card.id];
    if (!actuales.includes(card.id)) setSelectedCardIds(ids);
    const tarjeta = (event.currentTarget.closest('[data-card-id]') as HTMLElement | null)?.getBoundingClientRect();
    const ancho = 288;
    const x = tarjeta ? Math.min(window.innerWidth - ancho - 12, Math.max(12, tarjeta.right + 10)) : Math.round(window.innerWidth / 2);
    const y = tarjeta ? Math.min(window.innerHeight - 420, Math.max(72, tarjeta.top)) : 120;
    setSettingsPos({ x, y });
    setSettingsCardId(card.id);
  }, []);

  const idsDeAjustes = useMemo(
    () => (settingsCardId && selectedCardIds.includes(settingsCardId) ? selectedCardIds : settingsCardId ? [settingsCardId] : []),
    [selectedCardIds, settingsCardId],
  );

  const aplicarEstilo = useCallback((patch: Partial<NonNullable<BoardCard['estilo']>>) => {
    if (!idsDeAjustes.length) return;
    const ids = new Set(idsDeAjustes);
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((card) => (ids.has(card.id) ? { ...card, estilo: { ...(card.estilo ?? {}), ...patch } } : card)),
    }), { coalesceKey: `estilo:${idsDeAjustes.join(',')}` });
  }, [idsDeAjustes, updateBoard]);

  const aplicarColor = useCallback((color: BoardCard['color']) => {
    if (!idsDeAjustes.length) return;
    const ids = new Set(idsDeAjustes);
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((card) => (ids.has(card.id) ? { ...card, color } : card)),
    }));
  }, [idsDeAjustes, updateBoard]);

  const alternarBloqueoSeleccion = useCallback(() => {
    if (!idsDeAjustes.length) return;
    const ids = new Set(idsDeAjustes);
    updateBoard((board) => ({
      ...board,
      cards: board.cards.map((card) => (ids.has(card.id) ? { ...card, locked: !card.locked } : card)),
    }));
  }, [idsDeAjustes, updateBoard]);

  /** Convertir conserva posición, título y color; el tipo nuevo decide el contenido. */
  const convertirEn = useCallback((tipo: 'note' | 'marco' | 'columna') => {
    if (!idsDeAjustes.length) return;
    const ids = new Set(idsDeAjustes);
    updateBoard((board) => {
      const cardIds = new Set(board.cards.map((card) => card.id));
      return {
        ...board,
        cards: board.cards.map((card) => {
          if (!ids.has(card.id)) return card;
          if (tipo === 'marco') {
            return {
              ...card,
              type: 'marco',
              width: Math.max(320, card.width),
              height: undefined,
              media: undefined,
              datos: { ...normalizeFrameData(card.datos ?? {}, card.id, cardIds) },
            };
          }
          if (tipo === 'columna') {
            return {
              ...card,
              type: 'columna',
              width: Math.max(260, card.width),
              height: undefined,
              media: undefined,
              datos: { ...normalizeColumnData(card.datos ?? {}, card.id, cardIds) },
            };
          }
          return {
            ...card,
            type: 'note',
            width: Math.min(640, Math.max(210, card.width)),
            height: undefined,
            url: undefined,
            media: undefined,
            datos: undefined,
          };
        }),
      };
    });
    setNotice(tipo === 'note' ? 'Convertida en nota. Su contenido sigue editable.' : tipo === 'marco' ? 'Convertida en marco: arrastra otras tarjetas dentro.' : 'Convertida en columna: orden explícito y plegable.');
  }, [idsDeAjustes, updateBoard]);

  useEffect(() => {
    if (!settingsCardId) return;
    if (!activeBoard?.cards.some((card) => card.id === settingsCardId) || !selectedCardIds.includes(settingsCardId)) setSettingsCardId(null);
  }, [activeBoard?.cards, selectedCardIds, settingsCardId]);

  const crearRelacion = useCallback((from: string, to: string) => {
    if (!activeBoard || from === to) return false;
    const exists = activeBoard.relations.some((relation) => [relation.from, relation.to].sort().join(':') === [from, to].sort().join(':'));
    if (exists) {
      setNotice('Estas tarjetas ya están relacionadas.');
      return false;
    }
    updateBoard((board) => ({ ...board, relations: [...board.relations, { id: newBoardId('relation'), from, to }] }));
    setNotice('Conector creado. Doble clic sobre la curva para ponerle etiqueta.');
    return true;
  }, [activeBoard, updateBoard]);

  const iniciarConector = (card: BoardCard, event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0 || !activeBoard) return;
    const rect = viewportRef.current?.getBoundingClientRect();
    if (!rect) return;
    connectOrigin.current = { cardId: card.id, pointerId: event.pointerId };
    const mundo = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
    setConnectDraft({ from: card.id, x: event.clientX - rect.left, y: event.clientY - rect.top, mundo, target: null });
  };

  const conectorActivo = connectDraft !== null;
  useEffect(() => {
    if (!conectorActivo) return;
    const mover = (event: PointerEvent) => {
      const origin = connectOrigin.current;
      const rect = viewportRef.current?.getBoundingClientRect();
      if (!origin || !rect) return;
      const bajo = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-card-id]');
      const target = bajo?.dataset.cardId ?? null;
      const mundo = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
      setConnectDraft({ from: origin.cardId, x: event.clientX - rect.left, y: event.clientY - rect.top, mundo, target: target === origin.cardId ? null : target });
    };
    const soltar = (event: PointerEvent) => {
      const origin = connectOrigin.current;
      if (!origin) return;
      const bajo = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>('[data-card-id]');
      const target = bajo?.dataset.cardId ?? null;
      connectOrigin.current = null;
      setConnectDraft(null);
      if (target && target !== origin.cardId) crearRelacion(origin.cardId, target);
      else setNotice('Suelta el conector sobre otra tarjeta para relacionarlas.');
    };
    const cancelar = () => {
      connectOrigin.current = null;
      setConnectDraft(null);
    };
    window.addEventListener('pointermove', mover);
    window.addEventListener('pointerup', soltar);
    window.addEventListener('pointercancel', cancelar);
    return () => {
      window.removeEventListener('pointermove', mover);
      window.removeEventListener('pointerup', soltar);
      window.removeEventListener('pointercancel', cancelar);
    };
  }, [conectorActivo, crearRelacion]);

  const editarEtiquetaRelacion = (relation: BoardRelation) => {
    const valor = window.prompt('Etiqueta del conector (vacío para quitarla)', relation.label ?? '');
    if (valor === null) return;
    const label = valor.trim().slice(0, 160);
    updateBoard((board) => ({
      ...board,
      relations: board.relations.map((item) => item.id === relation.id
        ? { ...item, ...(label ? { label } : { label: undefined }) }
        : item),
    }));
  };

  const handleConnectCard = (cardId: string) => {
    if (!connectMode || !activeBoard) return;
    if (!connectFromId) {
      setConnectFromId(cardId);
      setNotice('Ahora elige otra tarjeta para crear la relación.');
      return;
    }
    if (connectFromId === cardId) {
      setConnectFromId(null);
      setNotice('Relación cancelada.');
      return;
    }
    crearRelacion(connectFromId, cardId);
    setConnectFromId(null);
  };

  const createBoardInProject = async (projectId: string, title = 'Nuevo tablero') => {
    const board = createBoard(title);
    await assignBoardToProject(board.id, projectId);
    setProjectIdByBoardId((current) => new Map(current).set(board.id, projectId));
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
  };

  const handleProjectSelect = async (projectId: string) => {
    if (!projects.some((project) => project.id === projectId)) return;
    if (!(await flushBoardWrites())) {
      setNotice('No se cambió de proyecto porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    try {
      await setActiveProject(projectId);
      setActiveProjectId(projectId);
      setProjectError(null);
      const nextBoard = boards.find((board) => projectIdByBoardId.get(board.id) === projectId);
      if (nextBoard) setActiveBoardId(nextBoard.id);
      else await createBoardInProject(projectId, 'Mi tablero');
      setSelectedCardIds([]);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo cambiar de proyecto.');
    }
  };

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = projectName.trim().slice(0, 120);
    if (!name) return;
    if (!(await flushBoardWrites())) {
      setNotice('No se creó el proyecto porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    try {
      const project = await createProject(name);
      setProjects((current) => [...current, project]);
      const board = createBoard('Mi tablero');
      await assignBoardToProject(board.id, project.id);
      await setActiveProject(project.id);
      setProjectIdByBoardId((current) => new Map(current).set(board.id, project.id));
      setBoards((current) => [...current, board]);
      setActiveProjectId(project.id);
      setActiveBoardId(board.id);
      setSelectedCardIds([]);
      enqueueBoardSave(board, { immediate: true });
      setProjectError(null);
      setProjectName('');
      setProjectDialog(false);
      setNotice('Proyecto creado. Tus tableros siguen guardándose localmente.');
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo crear el proyecto.');
    }
  };

  const handleSavePdfReference = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!activeProject || !activeBoard || !pdfReferenceSource) return;
    const reference = createPdfReference({
      projectId: activeProject.id,
      boardId: activeBoard.id,
      source: pdfReferenceSource,
      quote: pdfReferenceQuote,
      note: pdfReferenceNote,
    });
    if (!reference) {
      setNotice('No se pudo validar la referencia. Comprueba que el PDF y la página estén disponibles.');
      return;
    }
    try {
      await savePdfReference(reference);
      setProjectReferences((current) => [reference, ...current]);
      setPdfReferenceQuote('');
      setPdfReferenceNote('');
      setPdfReferenceDialog(false);
      setReferencesOpen(true);
      setNotice('Referencia guardada en el proyecto. No se copió el PDF.');
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo guardar la referencia PDF.');
    }
  };

  const handleOpenPdfReference = (reference: PdfReference) => {
    if (!onOpenPdfReference?.(reference)) {
      setNotice('Abre el mismo PDF en PROMETEO para saltar a esta página. La referencia conserva su huella SHA-256.');
      return;
    }
    setReferencesOpen(false);
    setNotice('PDF abierto en la página ' + reference.page + '.');
  };

  const handleDeletePdfReference = async (reference: PdfReference) => {
    try {
      await deletePdfReference(reference.id);
      void recordarBorrado({
        kind: 'reference',
        label: `Referencia a «${reference.sourceName}» · página ${reference.page}`,
        payload: { reference },
      });
      setProjectReferences((current) => current.filter((item) => item.id !== reference.id));
      mostrarAviso(`Referencia a «${reference.sourceName}» eliminada · 30 días en Archivo`, () => {
        setProjectReferences((current) => current.some((item) => item.id === reference.id) ? current : [reference, ...current]);
        void savePdfReference(reference).catch((error: unknown) => {
          setProjectError(error instanceof Error ? error.message : 'No se pudo recuperar la referencia PDF.');
        });
      });
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo eliminar la referencia PDF.');
    }
  };

  const exportProjectMarkdown = () => {
    if (!activeProject) return;
    downloadText(
      boardFilename(activeProject.name, 'md'),
      projectToMarkdown(activeProject, projectBoards, activeProjectReferences),
      'text/markdown;charset=utf-8',
    );
    setNotice('Markdown del proyecto listo para Obsidian. Los PDF permanecen en su ubicación original.');
  };

  const addNewBoard = async () => {
    if (!(await flushBoardWrites())) {
      setNotice('No se creó otro tablero porque el actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    if (activeProjectId) {
      try {
        await createBoardInProject(activeProjectId);
        return;
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar el tablero al proyecto.');
        return;
      }
    }
    const board = createBoard('Nuevo tablero');
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
  };

  const crearTableroAnidado = (destino: BoardDocument) => {
    setNestedDialog(false);
    const creada = addToolCard('tablero', (card) => {
      card.title = destino.title || 'Tablero';
      card.datos = { boardId: destino.id, boardTitle: destino.title || 'Tablero' };
    });
    if (creada) setNotice(`Tablero «${destino.title || 'sin título'}» anidado como tarjeta.`);
  };

  const abrirPlantillas = () => {
    setTemplates(listarPlantillas(activeProject?.plantillas ?? []));
    setTemplateDialog(true);
  };

  const aplicarPlantilla = async (plantilla: Plantilla) => {
    if (!(await flushBoardWrites())) {
      setNotice('No se aplicó la plantilla porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    const { cards, relations, title } = materializar(plantilla.board, plantilla.nombre);
    const board: BoardDocument = {
      ...createBoard(title.slice(0, 120)),
      cards,
      relations,
    };
    if (activeProjectId) {
      try {
        await assignBoardToProject(board.id, activeProjectId);
        setProjectIdByBoardId((current) => new Map(current).set(board.id, activeProjectId));
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar el tablero al proyecto.');
        return;
      }
    }
    setBoards((current) => [...current, board]);
    setActiveBoardId(board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(board, { immediate: true });
    setTemplateDialog(false);
    setNotice(`Tablero «${board.title}» creado desde la plantilla «${plantilla.nombre}».`);
  };

  const guardarTableroComoPlantilla = async () => {
    if (!activeBoard || !activeProject) return;
    const plantilla = crearPlantilla(activeBoard);
    try {
      const plantillas = await saveProjectPlantilla(activeProject.id, plantilla);
      setProjects((current) => current.map((project) => project.id === activeProject.id ? { ...project, plantillas } : project));
      setTemplates(listarPlantillas(plantillas));
      setNotice(`«${activeBoard.title}» guardado como plantilla del proyecto «${activeProject.name}».`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo guardar la plantilla en el proyecto.');
    }
  };

  const borrarPlantillaGuardada = async (id: string) => {
    if (!activeProject) return;
    try {
      const plantillas = await deleteProjectPlantilla(activeProject.id, id);
      setProjects((current) => current.map((project) => project.id === activeProject.id ? { ...project, plantillas } : project));
      setTemplates(listarPlantillas(plantillas));
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo eliminar la plantilla.');
    }
  };

  const commitProjectRename = async () => {
    if (!activeProject) return;
    const name = projectDraft.trim().slice(0, 120);
    setRenamingProject(false);
    if (!name || name === activeProject.name) return;
    try {
      const updated = await renameProject(activeProject.id, name);
      setProjects((current) => current.map((project) => project.id === updated.id ? updated : project));
      setProjectError(null);
      setNotice(`Proyecto renombrado a «${updated.name}».`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo renombrar el proyecto.');
    }
  };

  const archivarProyecto = async () => {
    if (!activeProject) return;
    try {
      const archivado = await setProjectArchived(activeProject.id, true);
      const restantes = projects.map((project) => project.id === archivado.id ? archivado : project);
      const siguiente = restantes.find((project) => !project.archivado);
      if (siguiente) {
        await setActiveProject(siguiente.id);
        setActiveProjectId(siguiente.id);
        const nextBoard = boards.find((board) => projectIdByBoardId.get(board.id) === siguiente.id);
        if (nextBoard) setActiveBoardId(nextBoard.id);
        else await createBoardInProject(siguiente.id, 'Mi tablero');
        setProjects(restantes);
      } else {
        const nuevo = await createProject('Proyecto general');
        await setActiveProject(nuevo.id);
        setProjects([...restantes, nuevo]);
        setActiveProjectId(nuevo.id);
        await createBoardInProject(nuevo.id, 'Mi tablero');
      }
      setSelectedCardIds([]);
      setNotice(`Proyecto «${archivado.name}» archivado. Está en Archivo y se puede recuperar.`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo archivar el proyecto.');
    }
  };

  const restaurarProyecto = async (projectId: string) => {
    try {
      const restaurado = await setProjectArchived(projectId, false);
      setProjects((current) => current.map((project) => project.id === restaurado.id ? restaurado : project));
      setNotice(`Proyecto «${restaurado.name}» restaurado.`);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo restaurar el proyecto.');
    }
  };

  const moverTableroAProyecto = async () => {
    if (!activeBoard || !moveTargetId) return;
    try {
      await assignBoardToProject(activeBoard.id, moveTargetId);
      setProjectIdByBoardId((current) => new Map(current).set(activeBoard.id, moveTargetId));
      await setActiveProject(moveTargetId);
      setActiveProjectId(moveTargetId);
      setMoveDialog(false);
      setSelectedCardIds([]);
      setNotice('Tablero movido de proyecto sin copiar sus tarjetas.');
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : 'No se pudo mover el tablero.');
    }
  };

  /** Borrar definitivamente exige el nombre escrito y deja 30 días de memoria. */
  const borrarProyectoDefinitivo = async (projectId: string) => {
    const project = projects.find((item) => item.id === projectId);
    if (!project) return;
    if (deleteProjectDraft.trim() !== project.name) {
      setArchiveError('Escribe el nombre exacto del proyecto para borrarlo definitivamente.');
      return;
    }
    setArchiveError(null);
    const projectBoardIds = boards.filter((board) => projectIdByBoardId.get(board.id) === project.id).map((board) => board.id);
    const projectBoardDocs = boards.filter((board) => projectBoardIds.includes(board.id));
    const links = projectBoardIds.map((boardId) => ({ boardId, projectId: project.id }));
    await recordarBorrado({
      kind: 'project',
      label: `Proyecto «${project.name}»`,
      payload: { project: { project, boards: projectBoardDocs, links } },
    });
    try {
      for (const boardId of projectBoardIds) {
        await removeBoardFromStore(boardId);
        try { await removeBoardProjectLink(boardId); } catch { /* el vínculo huérfano no bloquea */ }
      }
      await removeProjectRecord(project.id);
      const restantes = projects.filter((item) => item.id !== project.id);
      const siguiente = restantes.find((item) => !item.archivado);
      setProjects(restantes);
      setBoards((current) => current.filter((board) => !projectBoardIds.includes(board.id)));
      setProjectIdByBoardId((current) => {
        const next = new Map(current);
        projectBoardIds.forEach((id) => next.delete(id));
        return next;
      });
      setDeleteProjectId(null);
      setDeleteProjectDraft('');
      if (siguiente) {
        await setActiveProject(siguiente.id);
        setActiveProjectId(siguiente.id);
        const nextBoard = boards.find((board) => projectIdByBoardId.get(board.id) === siguiente.id && !projectBoardIds.includes(board.id));
        if (nextBoard) setActiveBoardId(nextBoard.id);
        else await createBoardInProject(siguiente.id, 'Mi tablero');
      } else {
        const nuevo = await createProject('Proyecto general');
        setProjects([...restantes, nuevo]);
        await setActiveProject(nuevo.id);
        setActiveProjectId(nuevo.id);
        await createBoardInProject(nuevo.id, 'Mi tablero');
      }
      setSelectedCardIds([]);
      setNotice(`Proyecto «${project.name}» borrado. Queda 30 días en Archivo.`);
      await refrescarArchivo();
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : 'No se pudo borrar el proyecto.');
    }
  };

  const renameBoard = (title: string) => {
    updateBoard((board) => ({ ...board, title: title.slice(0, 120) }));
  };

  const removeCurrentBoard = async () => {
    if (!activeBoard) return;
    const board = activeBoard;
    const projectId = projectIdByBoardId.get(board.id);
    if (!(await flushBoardWrites())) {
      setNotice('No se eliminó el tablero porque tiene cambios sin guardar. Reintenta o exporta una copia.');
      return;
    }
    void recordarBorrado({
      kind: 'board',
      label: `Tablero «${board.title || 'Sin título'}»`,
      payload: { board, ...(projectId ? { projectId } : {}) },
    });
    try {
      await removeBoardFromStore(board.id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo quitar el tablero guardado.');
      return;
    }
    try { await removeBoardProjectLink(board.id); } catch { /* El vínculo huérfano no borra referencias ni otros tableros. */ }
    const remaining = boards.filter((item) => item.id !== board.id);
    setProjectIdByBoardId((current) => {
      const next = new Map(current);
      next.delete(board.id);
      return next;
    });
    setSelectedCardIds([]);
    setConnectFromId(null);
    setBoards(remaining);
    const nextInProject = remaining.find((board) => !activeProjectId || projectIdByBoardId.get(board.id) === activeProjectId);
    if (nextInProject) {
      setActiveBoardId(nextInProject.id);
    } else {
      try {
        if (activeProjectId) await createBoardInProject(activeProjectId, 'Mi tablero');
        else {
          const fresh = createBoard('Mi tablero');
          setBoards([fresh]);
          setActiveBoardId(fresh.id);
          enqueueBoardSave(fresh, { immediate: true });
        }
      } catch (error) {
        setNotice(error instanceof Error ? error.message : 'No se pudo crear un tablero de reemplazo.');
      }
    }
    mostrarAviso(`Tablero «${board.title || 'Sin título'}» eliminado · 30 días en Archivo`, () => {
      setBoards((current) => current.some((item) => item.id === board.id) ? current : [board, ...current]);
      if (projectId) {
        setProjectIdByBoardId((current) => new Map(current).set(board.id, projectId));
        void assignBoardToProject(board.id, projectId).catch((error: unknown) => {
          setProjectError(error instanceof Error ? error.message : 'No se pudo recuperar el vínculo del tablero.');
        });
      }
      setActiveBoardId(board.id);
      setSelectedCardIds([]);
      enqueueBoardSave(board, { immediate: true });
    });
  };

  /** «Archivo» no es una papelera visible: es donde se puede recuperar lo que la memoria guardó. */
  const abrirArchivo = useCallback(async () => {
    setArchiveError(null);
    setArchiveOpen(true);
    setBorrados(await listarBorrados());
  }, []);

  const refrescarArchivo = useCallback(async () => {
    setBorrados(await listarBorrados());
  }, []);

  const restaurarEntrada = async (entry: BorradoEntry) => {
    setRestoringId(entry.id);
    setArchiveError(null);
    try {
      const tomado = await tomarBorrado(entry.id);
      if (!tomado) throw new Error('Esa entrada ya no está en la memoria de 30 días.');
      if (tomado.kind === 'board' && tomado.payload.board) {
        const board = normalizeBoard(tomado.payload.board);
        if (!board) throw new Error('El tablero guardado no se pudo leer.');
        if (tomado.payload.projectId) {
          try {
            await assignBoardToProject(board.id, tomado.payload.projectId);
            setProjectIdByBoardId((current) => new Map(current).set(board.id, tomado.payload.projectId!));
          } catch {
            /* El tablero se recupera igual aunque el proyecto ya no exista. */
          }
        }
        setBoards((current) => current.some((item) => item.id === board.id) ? current.map((item) => item.id === board.id ? board : item) : [board, ...current]);
        setActiveBoardId(board.id);
        setSelectedCardIds([]);
        enqueueBoardSave(board, { immediate: true });
        setNotice(`Tablero «${board.title || 'Sin título'}» recuperado.`);
      } else if (tomado.kind === 'reference' && tomado.payload.reference) {
        await savePdfReference(tomado.payload.reference);
        setProjectReferences((current) => current.some((item) => item.id === tomado.payload.reference!.id)
          ? current
          : [tomado.payload.reference!, ...current]);
        setNotice(`Referencia a «${tomado.payload.reference.sourceName}» recuperada.`);
      } else if (tomado.kind === 'cards' && tomado.payload.cards) {
        const { boardId, cards, relations } = tomado.payload.cards;
        updateBoardById(boardId, (board) => {
          const cardsById = new Map(cards.map((card) => [card.id, card]));
          const conMarcos = board.cards.map((item) => {
            if (item.type !== 'marco') return item;
            const data = readFrameData(item);
            const dentro = cards.filter((card) => {
              const caja = rectDeTarjeta(card);
              const centroX = caja.x + caja.width / 2;
              const centroY = caja.y + caja.height / 2;
              return centroX >= item.x && centroX <= item.x + item.width
                && centroY >= item.y && centroY <= item.y + readFrameData(item).alto;
            }).map((card) => card.id);
            if (!dentro.length) return item;
            return { ...item, datos: { ...item.datos, ...data, hijos: [...new Set([...data.hijos, ...dentro])] } };
          });
          return {
            ...board,
            cards: [...conMarcos, ...cardsById.values()],
            relations: [...board.relations, ...relations.filter((relation) => !board.relations.some((item) => item.id === relation.id))],
          };
        });
        // Las relaciones externas a las tarjetas borradas ya no existen; se conservan solo las internas.
        setNotice(`${cards.length} ${cards.length === 1 ? 'tarjeta recuperada' : 'tarjetas recuperadas'} en su tablero.`);
      } else if (tomado.kind === 'project' && tomado.payload.project) {
        const { project, boards: tablerosBorrados, links } = tomado.payload.project;
        await saveProjectRecord(project);
        setProjects((current) => current.some((item) => item.id === project.id) ? current : [...current, project]);
        for (const board of tablerosBorrados) {
          setBoards((current) => current.some((item) => item.id === board.id) ? current : [board, ...current]);
          enqueueBoardSave(board, { immediate: true });
        }
        for (const link of links) {
          try {
            await assignBoardToProject(link.boardId, link.projectId);
            setProjectIdByBoardId((current) => new Map(current).set(link.boardId, link.projectId));
          } catch {
            /* la memoria conserva el proyecto aunque un vínculo no se pueda rehacer */
          }
        }
        setNotice(`Proyecto «${project.name}» recuperado con ${tablerosBorrados.length} ${tablerosBorrados.length === 1 ? 'tablero' : 'tableros'}.`);
      }
      setBorrados((current) => current.filter((item) => item.id !== entry.id));
      await refrescarArchivo();
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : 'No se pudo recuperar la entrada.');
    } finally {
      setRestoringId(null);
    }
  };

  const olvidarEntrada = async (id: string) => {
    await olvidarBorrado(id);
    setBorrados((current) => current.filter((item) => item.id !== id));
  };


  const aplicarVistaPrevia = useCallback(async (cardId: string, url: string) => {
    try {
      const respuesta = await studioApi.vistaPreviaUrl(url);
      const preview = normalizarVistaPrevia(respuesta, url);
      if (!preview) {
        setNotice('El enlace se guardó, pero la página no publica título, descripción ni imagen.');
        return;
      }
      updateBoard((board) => ({
        ...board,
        cards: board.cards.map((card) => card.id === cardId
          ? {
            ...card,
            title: card.title && card.title !== card.url ? card.title : (preview.titulo || preview.sitio || card.title),
            datos: { ...card.datos, vistaPrevia: preview },
          }
          : card),
      }));
      setNotice('Vista previa añadida desde el motor local.');
    } catch {
      setNotice('El enlace se guardó. No se pudo leer la vista previa; puedes añadir una nota a mano.');
    } finally {
    }
  }, [updateBoard]);

  const desarmandoRef = useRef<string | null>(null);

  const mimeDeDataUrl = (dataUrl: string): string => {
    const match = /^data:([^;,]+)[;,]/.exec(dataUrl);
    return match?.[1] || 'image/png';
  };

  /** Pega una URL en un Referente: captura + enlace como original fijo y bloqueado. */
  const capturarUrlEnReferente = useCallback(async (cardId: string, url: string) => {
    const limpia = url.trim();
    if (!isSafeExternalUrl(limpia)) {
      setNotice('Usa una dirección web completa que empiece con http:// o https://.');
      return;
    }
    let preview: ReturnType<typeof normalizarVistaPrevia>;
    try {
      preview = normalizarVistaPrevia(await studioApi.vistaPreviaUrl(limpia), limpia);
    } catch {
      preview = undefined;
    }
    updateBoard((board) => {
      const card = board.cards.find((item) => item.id === cardId);
      if (!card) return board;
      const referente = leerReferente(card);
      const conImagen = preview?.imagen ? agregarImagenDesdeUrl(referente, preview.imagen) ?? referente : referente;
      const siguiente = {
        ...conImagen,
        nombre: preview?.titulo || conImagen.nombre || new URL(limpia).hostname,
        url: limpia,
        archivoOrigen: conImagen.archivoOrigen || new URL(limpia).hostname,
        porQue: conImagen.porQue || preview?.descripcion || '',
      };
      return {
        ...board,
        cards: board.cards.map((item) => item.id === cardId
          ? {
            ...item,
            title: siguiente.nombre || item.title,
            locked: true,
            datos: { ...item.datos, ...siguiente, vistaPrevia: preview },
          }
          : item),
      };
    });
    setNotice(preview?.imagen
      ? 'Captura y enlace guardados como original fijo. Pulsa «Desarmar» para separar sus piezas.'
      : 'Enlace guardado como original fijo. Pulsa «Desarmar» para descargar la captura y sus piezas.');
  }, [updateBoard]);

  /** Cualquier adjunto (PDF, vídeo, audio, archivo) entra en un Referente como copia local. */
  const adjuntarArchivosAReferente = useCallback(async (cardId: string, files: File[]) => {
    const validos = files.filter((file) => file.size <= MAX_MEDIA_BYTES);
    if (!validos.length) {
      setNotice(files.length ? 'Los adjuntos superan el límite de 12 MB.' : 'No hay archivos que adjuntar.');
      return;
    }
    try {
      const leidos = await Promise.all(validos.map(async (file) => ({
        name: file.name,
        mimeType: file.type || 'application/octet-stream',
        dataUrl: await readFileAsDataUrl(file),
        kind: (file.type.startsWith('image/') ? 'image' : file.type.startsWith('video/') ? 'video' : file.type.startsWith('audio/') ? 'audio' : 'file') as BoardMedia['kind'],
      })));
      updateBoard((board) => ({
        ...board,
        cards: board.cards.map((card) => {
          if (card.id !== cardId) return card;
          const referente = leerReferente(card);
          return { ...card, datos: { ...card.datos, ...referente, adjuntos: [...referente.adjuntos, ...leidos] } };
        }),
      }));
      setNotice(`${leidos.length} ${leidos.length === 1 ? 'adjunto guardado' : 'adjuntos guardados'} en el Referente.`);
    } catch {
      setNotice('No se pudieron leer los adjuntos.');
    }
  }, [updateBoard]);

  /**
   * Desarmar una URL: el backend descarga el HTML y las imágenes (sin JS ajeno),
   * guarda el original bloqueado y coloca piezas editables alrededor.
   */
  const desarmarEnReferente = useCallback(async (cardId: string, url: string) => {
    const limpia = url.trim();
    if (!isSafeExternalUrl(limpia)) {
      setNotice('La URL del referente no es válida.');
      return;
    }
    if (desarmandoRef.current) return;
    desarmandoRef.current = limpia;
    setNotice('Desarmando la página en piezas…');
    try {
      const respuesta = await studioApi.desarmarUrl(limpia);
      if (!respuesta.ok) {
        setNotice(respuesta.message || 'La página no se pudo desarmar.');
        return;
      }
      const piezas = (respuesta.piezas ?? []).slice(0, 28);
      const fecha = new Date().toISOString().slice(0, 10);
      let creadas = 0;
      updateBoard((board) => {
        const original = board.cards.find((card) => card.id === cardId);
        if (!original) return board;
        const referente = leerReferente(original);
        const captura = respuesta.captura
          ? [{
              name: `captura-${respuesta.host || 'pagina'}.${mimeDeDataUrl(respuesta.captura).includes('svg') ? 'svg' : 'png'}`,
              mimeType: mimeDeDataUrl(respuesta.captura),
              dataUrl: respuesta.captura,
              kind: 'image' as const,
              fuente: respuesta.url || limpia,
              fecha,
            }]
          : [];
        const actualizado: BoardCard = {
          ...original,
          locked: true,
          title: respuesta.titulo || original.title,
          datos: {
            ...original.datos,
            ...referente,
            nombre: respuesta.titulo || referente.nombre,
            url: respuesta.url || limpia,
            archivoOrigen: respuesta.host || referente.archivoOrigen,
            porQue: referente.porQue || respuesta.descripcion || '',
            imagenes: [...captura, ...referente.imagenes.filter((imagen) => imagen.fuente !== (respuesta.url || limpia) || !captura.length)],
          },
        };
        const nuevas: BoardCard[] = [];
        piezas.forEach((pieza, indice) => {
          const columna = indice % 2;
          const fila = Math.floor(indice / 2);
          const x = columna === 0 ? original.x + original.width + 44 : original.x - 320;
          const y = original.y + fila * 220;
          if (pieza.kind === 'image' && pieza.src) {
            const media: BoardMedia = {
              name: pieza.name || `imagen-${indice + 1}`,
              mimeType: pieza.mime || mimeDeDataUrl(pieza.src),
              dataUrl: pieza.src,
              kind: 'image',
              alt: pieza.alt ?? '',
            };
            const card = { ...createMediaCard(x, y, media), width: 280 };
            card.datos = { fuente: pieza.fuente, desarmadoDe: respuesta.url || limpia, pieza: 'image' };
            nuevas.push(card);
          } else if (pieza.kind === 'text' && pieza.text) {
            const card = createCard('note', x, y);
            card.title = pieza.rol === 'titular' ? 'Titular' : 'Texto';
            card.body = pieza.text;
            card.width = 280;
            card.datos = { fuente: pieza.fuente, desarmadoDe: respuesta.url || limpia, pieza: 'text' };
            nuevas.push(card);
          } else if (pieza.kind === 'color' && pieza.color) {
            const card = createCard('note', x, y);
            card.title = pieza.color;
            card.body = `Color de ${respuesta.host || 'la página'}`;
            card.width = 210;
            card.estilo = { background: pieza.color, textColor: '#111111' };
            card.datos = { fuente: pieza.fuente, desarmadoDe: respuesta.url || limpia, pieza: 'color' };
            nuevas.push(card);
          } else if (pieza.kind === 'font' && pieza.font) {
            const card = createCard('note', x, y);
            card.title = 'Tipografía';
            card.body = pieza.font;
            card.width = 250;
            const primera = pieza.font.split(',')[0].replace(/["']/g, '').trim();
            card.estilo = primera ? { fontFamily: primera } : undefined;
            card.datos = { fuente: pieza.fuente, desarmadoDe: respuesta.url || limpia, pieza: 'font' };
            nuevas.push(card);
          }
        });
        creadas = nuevas.length;
        const previas = new Set(board.cards.filter((card) => card.id !== original.id && card.datos?.desarmadoDe === (respuesta.url || limpia)).map((card) => card.id));
        return {
          ...board,
          cards: [...board.cards.map((card) => card.id === original.id ? actualizado : card).filter((card) => !previas.has(card.id)), ...nuevas],
        };
      });
      setSelectedCardIds([cardId]);
      const guardadas = respuesta.archivos?.length ?? 0;
      setNotice(`Página desarmada en ${creadas} ${creadas === 1 ? 'pieza editable' : 'piezas editables'}. El original quedó bloqueado.${guardadas ? ` ${guardadas} imágenes guardadas en el proyecto.` : ''}`);
    } catch (error) {
      setNotice(error instanceof Error ? `No se pudo desarmar: ${error.message}` : 'No se pudo desarmar la página.');
    } finally {
      desarmandoRef.current = null;
    }
  }, [updateBoard]);

  useEffect(() => {
    desarmarRef.current = (cardId, url) => { void desarmarEnReferente(cardId, url); };
    adjuntarRef.current = (cardId, files) => { void adjuntarArchivosAReferente(cardId, files); };
    capturarUrlRef.current = (cardId, url) => { void capturarUrlEnReferente(cardId, url); };
  }, [adjuntarArchivosAReferente, capturarUrlEnReferente, desarmarEnReferente]);

  const accionesHerramientas = useMemo(() => ({ desarmarUrl: (cardId: string, url: string) => { void desarmarEnReferente(cardId, url); } }), [desarmarEnReferente]);

  const saveLinkCard = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isSafeExternalUrl(linkUrl)) {
      setLinkError('Usa una dirección web completa que empiece con http:// o https://.');
      return;
    }
    if (!activeBoard) return;
    const url = linkUrl.trim();
    const created = addToolCard('link', (card) => {
      card.title = linkTitle.trim() || url;
      card.url = url;
    }, linkPointRef.current ?? undefined);
    linkPointRef.current = null;
    if (!created) return;
    setLinkDialog(false);
    setLinkTitle('');
    setLinkUrl('');
    setLinkError(null);
    void aplicarVistaPrevia(created.id, url);
  };

  const addMedia = useCallback(async (file?: File, at?: { x: number; y: number }) => {
    if (!file || !activeBoard) return;
    if (file.size > MAX_MEDIA_BYTES) {
      setNotice('Este prototipo guarda archivos de hasta 12 MB. Reduce el tamaño y vuelve a intentarlo.');
      return;
    }
    try {
      const mimeType = file.type || 'application/octet-stream';
      const dataUrl = await readFileAsDataUrl(file);
      const kind = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : mimeType.startsWith('audio/') ? 'audio' : 'file';
      const media: BoardMedia = { name: file.name, mimeType, dataUrl, kind };
      const tamano = kind === 'image' || kind === 'video' ? await medirMedio(dataUrl, kind) : null;
      // addToolCard coloca desde el centro del objeto: se compensa el ancho real al soltar.
      const destino = at && tamano
        ? { x: at.x - tamano.width / 2 + 130, y: at.y - tamano.height / 2 + 90 }
        : at;
      const created = addToolCard('media', (card) => {
        card.title = media.name.replace(/\.[^.]+$/, '') || 'Recurso';
        card.media = media;
        if (tamano) {
          card.width = tamano.width;
          card.height = tamano.height;
        }
      }, destino);
      if (!created) return;
      setNotice(tamano
        ? `${kind === 'video' ? 'Vídeo' : 'Imagen'} libre añadido a resolución completa.`
        : 'Recurso añadido y guardado dentro del tablero local.');
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo añadir el archivo.');
    }
  }, [activeBoard, addToolCard]);

  const addMediaRef = useRef(addMedia);
  useEffect(() => {
    addMediaRef.current = addMedia;
  }, [addMedia]);

  const importBoard = async (file?: File) => {
    if (!file) return;
    try {
      if (!(await flushBoardWrites())) throw new Error('El tablero actual no se guardó; el archivo no se importó. Reintenta o exporta una copia.');
      const contents = await file.text();
      const imported = file.name.toLocaleLowerCase().endsWith('.md') ? markdownToBoard(contents) : parseBoardImport(JSON.parse(contents));
      if (!imported) throw new Error('El archivo no tiene un tablero de Prometeo válido.');
      const copy = cloneBoardForImport(imported);
      if (activeProjectId) await assignBoardToProject(copy.id, activeProjectId);
      setBoards((current) => [...current, copy]);
      if (activeProjectId) setProjectIdByBoardId((current) => new Map(current).set(copy.id, activeProjectId));
      setActiveBoardId(copy.id);
      setSelectedCardIds([]);
      enqueueBoardSave(copy, { immediate: true });
      setNotice(file.name.toLocaleLowerCase().endsWith('.md') ? 'Markdown importado como un tablero nuevo.' : 'Copia del tablero importada.');
      setLoadError(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo importar el archivo.');
    }
  };

  /** Crea o actualiza «Biblioteca» con la semilla de referentes, sin duplicar tarjetas. */
  const importReferentes = async () => {
    if (!(await flushBoardWrites())) {
      setNotice('No se importaron los referentes porque el tablero actual aún no se pudo guardar. Reintenta o exporta una copia.');
      return;
    }
    const result = importarBiblioteca(boards, undefined, {
      projectId: activeProjectId || undefined,
      projectIdByBoardId,
    });
    if (result.created && activeProjectId) {
      try {
        await assignBoardToProject(result.board.id, activeProjectId);
      } catch (error) {
        setProjectError(error instanceof Error ? error.message : 'No se pudo asignar la Biblioteca al proyecto.');
        return;
      }
      setProjectIdByBoardId((current) => new Map(current).set(result.board.id, activeProjectId));
    }
    setBoards((current) => current.some((board) => board.id === result.board.id)
      ? current.map((board) => board.id === result.board.id ? result.board : board)
      : [...current, result.board]);
    setActiveBoardId(result.board.id);
    setSelectedCardIds([]);
    enqueueBoardSave(result.board, { immediate: true });
    setNotice(result.created
      ? `Tablero «Biblioteca» creado con ${result.referentes} referentes en ${result.marcos} marcos.`
      : `Tablero «Biblioteca» actualizado: ${result.referentes} referentes en ${result.marcos} marcos, sin duplicados.`);
  };

  /** Suma los ♥/✕ de un `gustos-parcial.json` a la memoria del proyecto activo. */
  const importGustos = async (file?: File) => {
    if (!file) return;
    if (!activeProject) {
      setNotice('Entropía necesita un proyecto activo para recordar el gusto.');
      return;
    }
    if (file.size > 2_000_000) {
      setNotice('El archivo de gustos es demasiado grande (máximo 2 MB).');
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setNotice('El archivo de gustos no es un JSON válido.');
      return;
    }
    const resultado = importarGustosParciales(activeProject.gustos, parsed);
    if (!resultado.likes && !resultado.nopes) {
      setNotice('El archivo no tiene votos de Entropía válidos.');
      return;
    }
    actualizarGustosProyecto(() => resultado.gustos);
    setNotice(`Gustos importados: ${resultado.likes} ♥ y ${resultado.nopes} ✕${resultado.ignorados ? `; ${resultado.ignorados} ignorados` : ''}.`);
  };

  const exportJson = () => {
    if (!activeBoard) return;
    downloadText(boardFilename(activeBoard.title, 'json'), JSON.stringify(makeBoardExport(activeBoard), null, 2), 'application/json');
    setNotice('El tablero y sus adjuntos se exportaron en JSON.');
  };

  const exportMarkdown = () => {
    if (!activeBoard) return;
    const markdown = boardToMarkdown(activeBoard, {
      cardMarkdown: (card) => {
        const tool = getBoardTool(card.type);
        return tool?.exportarMarkdown ? tool.exportarMarkdown(card) : null;
      },
    });
    downloadText(boardFilename(activeBoard.title, 'md'), markdown, 'text/markdown;charset=utf-8');
    setNotice('Markdown listo para Obsidian. Los adjuntos multimedia permanecen en la exportación JSON.');
  };

  /** Un .md por referente con frontmatter y enlaces [[ ]] a los del mismo marco. */
  const exportReferentesObsidian = () => {
    const notas = notasObsidian(projectBoards);
    if (!notas.length) {
      setNotice('No hay referentes que exportar. Importa la biblioteca primero.');
      return;
    }
    const bytes = construirZipObsidian(projectBoards);
    const url = URL.createObjectURL(new Blob([bytes.buffer as ArrayBuffer], { type: 'application/zip' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = activeProject ? `${boardFilename(activeProject.name, 'md').replace(/\.md$/, '')}-referentes.zip` : 'referentes-obsidian.zip';
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    setNotice(`Obsidian: ${notas.length} ${notas.length === 1 ? 'nota' : 'notas'} de referente en un ZIP.`);
  };

  const updateCard = (id: string, patch: Partial<BoardCard>) => {
    const field = Object.keys(patch)[0];
    const coalesceKey = field === 'title' || field === 'body' ? `card:${id}:${field}:${textSession.current}` : undefined;
    updateBoard((board) => ({ ...board, cards: board.cards.map((card) => card.id === id ? { ...card, ...patch } : card) }), { coalesceKey });
  };

  /** Reemplaza el medio conservando caja, posición, pie, alt y recorte. */
  const reemplazarMedia = async (cardId: string, file: File) => {
    if (!activeBoard) return;
    if (file.size > MAX_MEDIA_BYTES) {
      setNotice('El archivo supera los 12 MB. Reduce su tamaño y vuelve a intentarlo.');
      return;
    }
    const card = activeBoardRef.current?.cards.find((item) => item.id === cardId);
    if (!card) return;
    try {
      const mimeType = file.type || 'application/octet-stream';
      const kind = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : 'file';
      if (kind !== 'image' && kind !== 'video') {
        setNotice('Reemplaza una imagen o un vídeo por otro medio del mismo tipo.');
        return;
      }
      const dataUrl = await readFileAsDataUrl(file);
      const media: BoardMedia = { name: file.name, mimeType, dataUrl, kind };
      const anterior = card.media;
      updateCard(cardId, {
        media,
        title: card.title || media.name.replace(/\.[^.]+$/, ''),
        datos: {
          ...card.datos,
          ...(anterior ? { mediaAnterior: { ...anterior, reemplazado: new Date().toISOString() } } : {}),
        },
      });
      mostrarAviso('Imagen reemplazada · la caja y la leyenda no se movieron', undefined, true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo reemplazar el medio.');
    }
  };

  /** «Ver como» del marco: cambiar de vista no mueve ni borra ninguna tarjeta. */
  const updateFrameView = (id: string, vista: FrameView) => {
    updateBoard((board) => ({ ...board, cards: setFrameView(board.cards, id, vista) }));
  };

  /**
   * Publica la vista actual del marco como carpeta estática local.
   * La carpeta la elige la persona; no se envía nada por la red.
   */
  const publishFrame = async (card: BoardCard) => {
    const data = readFrameData(card);
    if (data.vista === 'libre') {
      setNotice('Elige Archivo, Muro o Mesa de luz antes de publicar.');
      return;
    }
    if (!activeBoard || publishingFrameId) return;
    setPublishingFrameId(card.id);
    setNotice('Eligiendo carpeta y preparando la publicación local…');
    try {
      const result = await publishFrameToDirectory(card.title || 'Archivo', data.vista, activeBoard.cards, data.hijos);
      setNotice(result.cancelled
        ? 'Publicación cancelada.'
        : result.zip
          ? `ZIP descargado: ${result.files} archivos (${result.media} ${result.media === 1 ? 'pieza' : 'piezas'}). Descomprímelo y abre index.html sin servidor.`
          : `Publicado en «${result.folder}»: ${result.files} archivos (${result.media} ${result.media === 1 ? 'pieza' : 'piezas'}). Abre index.html sin servidor.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo publicar el marco.');
    } finally {
      setPublishingFrameId(null);
    }
  };

  /**
   * Crea un marco nuevo en vista Archivo con el manifiesto como nota fija y
   * los collages de la semana convertidos en piezas del feed.
   */
  const crearManifiesto = async () => {
    if (!activeBoard || manifesting) return;
    const sourceBoards = projectBoards.length ? projectBoards : [activeBoard];
    const ahora = new Date();
    const seleccion = seleccionarSemana(sourceBoards, {
      ahora,
      gustos: activeProject?.gustos ?? gustosVacios(),
    });
    if (!seleccion.collages.length && !seleccion.lecturas.length && !seleccion.pesos.length) {
      setNotice('No hay nada que contar esta semana: faltan collages con ♥, lecturas aceptadas o pesos que hayan subido.');
      return;
    }
    setManifesting(true);
    try {
      const resultado = await pedirManifiesto(seleccion, activeProject?.name || activeBoard.title || 'el proyecto abierto');
      const maxX = activeBoard.cards.length
        ? Math.max(...activeBoard.cards.map((card) => card.x + card.width))
        : 0;
      const minY = activeBoard.cards.length
        ? Math.min(...activeBoard.cards.map((card) => card.y))
        : 0;
      const { frame, cards } = crearMarcoManifiesto(seleccion, resultado.lineas, {
        x: maxX + 80,
        y: minY,
        fuentes: fuentesEntropia,
        ahora,
      });
      setPropuestaManifiesto({ frame, cards });
      setNotice(resultado.disponible
        ? 'Propuesta de manifiesto lista en el lienzo. Enter o clic la acepta; Esc la descarta.'
        : `Sin DeepSeek (${resultado.motivo}). Hay una propuesta con 12 líneas vacías para escribir a mano. Enter o clic la acepta; Esc la descarta.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo crear el manifiesto.');
    } finally {
      setManifesting(false);
    }
  };

  const aceptarManifiesto = useCallback(() => {
    const propuesta = propuestaManifiesto;
    if (!propuesta) return;
    updateBoard((board) => ({ ...board, cards: [...board.cards, ...propuesta.cards] }));
    setSelectedCardIds([propuesta.frame.id]);
    setPropuestaManifiesto(null);
    setNotice('Manifiesto aceptado. Ya forma parte del tablero.');
  }, [propuestaManifiesto, updateBoard]);

  const descartarManifiesto = useCallback(() => {
    setPropuestaManifiesto(null);
    setNotice('Propuesta descartada. El tablero no cambió.');
  }, []);

  useEffect(() => {
    if (!propuestaManifiesto) return;
    const alTeclear = (event: KeyboardEvent) => {
      if (esObjetivoDeTexto(event.target)) return;
      if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        aceptarManifiesto();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        descartarManifiesto();
      }
    };
    window.addEventListener('keydown', alTeclear, true);
    return () => window.removeEventListener('keydown', alTeclear, true);
  }, [aceptarManifiesto, descartarManifiesto, propuestaManifiesto]);

  /** Las herramientas entregan la tarjeta completa; se conserva el agrupado de deshacer por campo de texto. */
  const replaceCard = useCallback((next: BoardCard) => {
    const current = activeBoard?.cards.find((card) => card.id === next.id);
    if (!current) return;
    const changed = (Object.keys(next) as Array<keyof BoardCard>).filter((key) => next[key] !== current[key]);
    const field = changed.length === 1 ? changed[0] : null;
    const coalesceKey = field === 'title' || field === 'body' ? `card:${next.id}:${field}:${textSession.current}` : undefined;
    updateBoard((board) => ({ ...board, cards: board.cards.map((card) => card.id === next.id ? next : card) }), { coalesceKey });
  }, [activeBoard, updateBoard]);

  /** La memoria de gusto vive en el proyecto y se escribe en su propio almacén. */
  const actualizarGustosProyecto = useCallback((actualizar: (gustos: Gustos) => Gustos) => {
    if (!activeProject) {
      setNotice('Entropía necesita un proyecto activo para recordar el gusto.');
      return;
    }
    const siguiente = actualizar(activeProject.gustos);
    setProjects((current) => current.map((project) =>
      project.id === activeProject.id
        ? { ...project, gustos: siguiente, updatedAt: new Date().toISOString() }
        : project,
    ));
    void saveProjectGustos(activeProject.id, siguiente).catch((error: unknown) => {
      setNotice(error instanceof Error ? error.message : 'No se pudo guardar la memoria de gusto.');
    });
  }, [activeProject]);

  /** Tira con una semilla (nueva o la indicada) y deja la tirada dentro del marco. */
  const tirarEnMarcoEntropia = (card: BoardCard, semilla: string = nuevaSemilla()) => {
    const frame = readFrameData(card);
    const tamano = { ancho: Math.max(120, card.width), alto: Math.max(120, frame.alto - 96) };
    try {
      const tirada = tirarEntropia({
        semilla,
        fuentes: fuentesEntropia,
        herramientas: listBoardTools().map((tool) => ({ id: tool.id, nombre: tool.nombre })),
        tamano,
        gustos: activeProject?.gustos ?? gustosVacios(),
      });
      updateCard(card.id, { datos: { ...card.datos, ...tirada } });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo tirar la combinación.');
    }
  };

  const combinacionDeTirada = (datos: EntropiaDatos) => ({
    semilla: datos.semilla,
    referentes: datos.fuentes,
    herramienta: datos.herramienta,
    regla: datos.regla,
    restriccion: datos.restriccion,
    azarPuro: datos.azarPuro,
  });

  /** ♥ guarda una copia con procedencia y suma 1 a los gustos del proyecto. */
  const guardarCollageEntropia = (card: BoardCard) => {
    const datos = leerEntropia(card);
    if (!datos) return;
    const guardado: EntropiaDatos = { ...datos, guardado: true, creado: new Date().toISOString() };
    const nueva: BoardCard = {
      ...card,
      id: newBoardId('card'),
      x: card.x + card.width + 32,
      y: card.y,
      title: `Collage · ${datos.reglaNombre || datos.regla}`,
      datos: { ...card.datos, ...guardado, hijos: [], vista: 'libre' },
    };
    updateBoard((board) => ({ ...board, cards: [...board.cards, nueva] }));
    setSelectedCardIds([nueva.id]);
    actualizarGustosProyecto((gustos) => like(gustos, combinacionDeTirada(datos)));
    setNotice(`Collage guardado con la semilla ${datos.semilla}.`);
  };

  /** ✕ solo resta 1 a los gustos; la tirada se queda como estaba. */
  const descartarCollageEntropia = (card: BoardCard) => {
    const datos = leerEntropia(card);
    if (!datos) return;
    actualizarGustosProyecto((gustos) => nope(gustos, combinacionDeTirada(datos)));
    setNotice('Entropía: «no» recordado sin tocar el collage.');
  };

  const lastArrow = useRef<{ clave: string; at: number }>({ clave: '', at: 0 });
  const lastResize = useRef<{ clave: string; at: number }>({ clave: '', at: 0 });

  /** Borra N tarjetas en un solo paso de historial y ofrece deshacer durante 5 s. */
  const deleteCards = useCallback((ids: readonly string[]) => {
    const board = activeBoardRef.current ?? activeBoard;
    if (!board || !ids.length) return 0;
    const seleccionadas = new Set(ids);
    const bloqueadas = board.cards.filter((card) => seleccionadas.has(card.id) && card.locked);
    const eliminables = board.cards
      .filter((card) => seleccionadas.has(card.id) && !card.locked)
      .map((card) => card.id);
    if (!eliminables.length) {
      setNotice('Todas las tarjetas seleccionadas están bloqueadas.');
      return 0;
    }
    updateBoard((actual) => borrarTarjetas(actual, eliminables));
    const borradas = new Set(eliminables);
    const eliminadas = board.cards.filter((card) => borradas.has(card.id));
    void recordarBorrado({
      kind: 'cards',
      label: `${eliminadas.length} ${eliminadas.length === 1 ? 'tarjeta' : 'tarjetas'} de «${board.title || 'Sin título'}»`,
      payload: {
        cards: {
          boardId: board.id,
          cards: eliminadas,
          relations: board.relations.filter((relation) => borradas.has(relation.from) || borradas.has(relation.to)),
        },
      },
    });
    setSelectedCardIds((current) => current.filter((id) => !borradas.has(id)));
    const cantidad = eliminables.length;
    const bloqueo = bloqueadas.length
      ? ` · ${bloqueadas.length} ${bloqueadas.length === 1 ? 'bloqueada se queda' : 'bloqueadas se quedan'}`
      : '';
    mostrarAviso(
      `${cantidad} ${cantidad === 1 ? 'tarjeta eliminada' : 'tarjetas eliminadas'}${bloqueo} · 30 días en Archivo`,
      undefined,
      true,
    );
    return cantidad;
  }, [activeBoard, mostrarAviso, updateBoard]);

  const removeCard = (id: string) => {
    deleteCards([id]);
  };

  const deleteSelectedCards = () => {
    deleteCards(selectedCardIds);
  };

  const copiarSeleccion = useCallback((cortar: boolean) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const seleccionadas = board.cards.filter((card) => selectedCardIds.includes(card.id));
    const marca = copiarTarjetas(board, selectedCardIds);
    if (!marca) return;
    // Al portapapeles del sistema van la marca interna y texto legible para otras apps.
    const texto = `${marca}\n\n${textoLegibleDeTarjetas(seleccionadas)}`;
    try {
      void navigator.clipboard?.writeText(texto).catch(() => { /* el portapapeles interno sigue disponible */ });
    } catch {
      /* Sin permiso de portapapeles la copia interna funciona igual. */
    }
    if (cortar) deleteCards(selectedCardIds);
  }, [deleteCards, selectedCardIds]);

  const pegarSeleccion = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board) return false;
    const resultado = pegarTarjetasEn(board, puntoDePegado());
    if (!resultado) return false;
    updateBoard(() => resultado.board);
    setSelectedCardIds(resultado.newIds);
    return true;
  }, [updateBoard]);

  const duplicarSeleccionActual = useCallback(() => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    let nuevos: string[] = [];
    updateBoard((actual) => {
      const duplicado = duplicarSeleccion(actual, selectedCardIds);
      nuevos = duplicado.newIds;
      return duplicado.board;
    });
    if (nuevos.length) setSelectedCardIds(nuevos);
  }, [selectedCardIds, updateBoard]);

  const moverSeleccion = useCallback((dx: number, dy: number) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const ids = tarjetasAMover(board, selectedCardIds);
    if (!ids.length) return;
    const ahora = Date.now();
    const clave = claveDeRafaga(lastArrow.current.clave, lastArrow.current.at, ahora);
    lastArrow.current = { clave, at: ahora };
    updateBoard((actual) => moverTarjetas(actual, ids, dx, dy), { coalesceKey: clave });
  }, [selectedCardIds, updateBoard]);

  /** ⌘+flechas · el mismo cambio de tamaño que un asa, sin ratón. */
  const redimensionarSeleccion = useCallback((dw: number, dh: number) => {
    const board = activeBoardRef.current;
    if (!board || !selectedCardIds.length) return;
    const ids = new Set(selectedCardIds);
    const ahora = Date.now();
    const clave = claveDeRafaga(lastResize.current.clave, lastResize.current.at, ahora);
    lastResize.current = { clave, at: ahora };
    const limitar = (valor: number, min: number, max: number) => Math.max(min, Math.min(max, valor));
    updateBoard((actual) => ({
      ...actual,
      cards: actual.cards.map((card) => {
        if (!ids.has(card.id) || card.locked) return card;
        if (card.type === 'marco') {
          const data = readFrameData(card);
          return {
            ...card,
            width: limitar(card.width + dw, FRAME_MIN_SIZE, 2400),
            datos: { ...card.datos, ...data, alto: limitar(data.alto + dh, FRAME_MIN_SIZE, 100000) },
          };
        }
        if (card.type === 'columna') return { ...card, width: limitar(card.width + dw, 210, 2400) };
        if (card.type === 'media' && (card.media?.kind === 'image' || card.media?.kind === 'video')) {
          return {
            ...card,
            width: limitar(card.width + dw, 80, 1200),
            height: limitar((card.height ?? Math.round(card.width * 0.75)) + dh, 60, 2400),
          };
        }
        // Nota y enlace: solo ancho; el alto sigue al contenido (A-1 · D4).
        return { ...card, width: limitar(card.width + dw, 210, 640) };
      }),
    }), { coalesceKey: clave });
  }, [selectedCardIds, updateBoard]);

  const ordenarSeleccion = useCallback((modo: 'adelante' | 'atras' | 'frente' | 'fondo') => {
    if (!selectedCardIds.length) return;
    updateBoard((board) => ({ ...board, cards: reordenarTarjetas(board.cards, selectedCardIds, modo) }));
  }, [selectedCardIds, updateBoard]);

  /** Esc cierra primero lo que esté abierto; si no hay nada, deselecciona. */
  const cerrarAlgo = (event: KeyboardEvent): boolean => {
    if (indexOpen) {
      event.preventDefault();
      cerrarIndice(true);
      return true;
    }
    if (shortcutsOpen) {
      event.preventDefault();
      setShortcutsOpen(false);
      return true;
    }
    if (templateDialog) {
      event.preventDefault();
      setTemplateDialog(false);
      return true;
    }
    if (nestedDialog) {
      event.preventDefault();
      setNestedDialog(false);
      return true;
    }
    if (linkDialog) {
      event.preventDefault();
      setLinkDialog(false);
      return true;
    }
    if (projectDialog) {
      event.preventDefault();
      setProjectDialog(false);
      return true;
    }
    if (moveDialog) {
      event.preventDefault();
      setMoveDialog(false);
      return true;
    }
    if (pdfReferenceDialog) {
      event.preventDefault();
      setPdfReferenceDialog(false);
      return true;
    }
    if (referencesOpen) {
      event.preventDefault();
      setReferencesOpen(false);
      return true;
    }
    if (mirarOpen) {
      event.preventDefault();
      setMirarOpen(false);
      return true;
    }
    if (archiveFullscreenId) {
      event.preventDefault();
      setArchiveFullscreenId(null);
      return true;
    }
    if (exportMenuOpen) {
      event.preventDefault();
      setExportMenuOpen(false);
      return true;
    }
    if (libraryMenuOpen) {
      event.preventDefault();
      setLibraryMenuOpen(false);
      return true;
    }
    if (frameToolId) {
      event.preventDefault();
      frameDraw.current = null;
      setFrameDraft(null);
      setFrameToolId(null);
      setNotice(null);
      return true;
    }
    if (addMenuOpen) {
      event.preventDefault();
      setAddMenuOpen(false);
      return true;
    }
    const enfocado = document.activeElement as HTMLElement | null;
    if (enfocado?.closest('[data-card-id]') && !enfocado.closest('input, textarea, select')) {
      event.preventDefault();
      enfocado.blur();
      viewportRef.current?.focus({ preventScroll: true });
      return true;
    }
    if (selectedCardIds.length) {
      event.preventDefault();
      setSelectedCardIds([]);
      return true;
    }
    return false;
  };

  /** Despachador único: la tabla ya decidió la acción; aquí solo se ejecuta. */
  const ejecutarAtajo = (atajo: AtajoLienzo, event: KeyboardEvent) => {
    if (shortcutsOpen && atajo.accion !== 'cerrar' && atajo.accion !== 'ayuda') return;

    if (atajo.accion === 'cerrar') {
      cerrarAlgo(event);
      return;
    }
    if (atajo.accion === 'ayuda') {
      event.preventDefault();
      setShortcutsOpen((open) => !open);
      setAddMenuOpen(false);
      return;
    }
    if (atajo.accion === 'pan') {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('button, a, [role="button"], [role="menuitem"], [role="option"], [role="tab"]')) return;
      event.preventDefault();
      spaceHeld.current = true;
      setSpacePanActive(true);
      return;
    }
    if (atajo.accion === 'herramientas') {
      if (archiveFullscreenId) return;
      event.preventDefault();
      if (!addMenuOpen) {
        addPointRef.current = lastPointerWorld.current
          ?? screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, cameraRef.current);
      }
      setAddMenuOpen((open) => !open);
      return;
    }
    if (atajo.accion === 'buscar') {
      event.preventDefault();
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
      return;
    }
    if (atajo.accion === 'indice') {
      event.preventDefault();
      if (indexOpen) cerrarIndice(true);
      else abrirIndice();
      return;
    }
    if (atajo.accion === 'renombrarProyecto') {
      if (!activeProject) return;
      event.preventDefault();
      setProjectDraft(activeProject.name);
      setRenamingProject(true);
      return;
    }
    if (atajo.accion === 'zoom100') {
      event.preventDefault();
      zoomTo(1);
      return;
    }
    if (atajo.accion === 'zoomIn') {
      event.preventDefault();
      zoomBy(1.2);
      return;
    }
    if (atajo.accion === 'zoomOut') {
      event.preventDefault();
      zoomBy(1 / 1.2);
      return;
    }
    if (atajo.accion === 'zoomFit') {
      event.preventDefault();
      fitBoard();
      return;
    }
    if (atajo.accion === 'zoomSelection') {
      event.preventDefault();
      fitSelection();
      return;
    }
    if (atajo.accion === 'deshacer') {
      event.preventDefault();
      undo();
      return;
    }
    if (atajo.accion === 'rehacer') {
      event.preventDefault();
      redo();
      return;
    }
    if (atajo.accion === 'seleccionarTodo') {
      event.preventDefault();
      setSelectedCardIds(seleccionarTodoElTablero(activeBoardRef.current ?? activeBoard!, framedChildIds));
      return;
    }
    if (atajo.accion === 'pegar') {
      // El evento paste decide: imagen o texto del sistema primero, copia interna después.
      return;
    }
    if (atajo.accion === 'copiar' || atajo.accion === 'cortar') {
      if (!selectedCardIds.length) return;
      event.preventDefault();
      copiarSeleccion(atajo.accion === 'cortar');
      return;
    }
    if (!selectedCardIds.length) return;
    event.preventDefault();
    switch (atajo.accion) {
      case 'borrar':
        deleteCards(selectedCardIds);
        break;
      case 'duplicar':
        duplicarSeleccionActual();
        break;
      case 'agrupar':
        agruparSeleccion();
        break;
      case 'desagrupar':
        desagruparSeleccion();
        break;
      case 'moverIzquierda':
        moverSeleccion(-1, 0);
        break;
      case 'moverDerecha':
        moverSeleccion(1, 0);
        break;
      case 'moverArriba':
        moverSeleccion(0, -1);
        break;
      case 'moverAbajo':
        moverSeleccion(0, 1);
        break;
      case 'moverIzquierda10':
        moverSeleccion(-10, 0);
        break;
      case 'moverDerecha10':
        moverSeleccion(10, 0);
        break;
      case 'moverArriba10':
        moverSeleccion(0, -10);
        break;
      case 'moverAbajo10':
        moverSeleccion(0, 10);
        break;
      case 'redimensionarAnchoMenos':
        redimensionarSeleccion(-10, 0);
        break;
      case 'redimensionarAnchoMas':
        redimensionarSeleccion(10, 0);
        break;
      case 'redimensionarAltoMenos':
        redimensionarSeleccion(0, -10);
        break;
      case 'redimensionarAltoMas':
        redimensionarSeleccion(0, 10);
        break;
      case 'traerAdelante':
        ordenarSeleccion('adelante');
        break;
      case 'enviarAtras':
        ordenarSeleccion('atras');
        break;
      case 'alFrente':
        ordenarSeleccion('frente');
        break;
      case 'alFondo':
        ordenarSeleccion('fondo');
        break;
      default:
        break;
    }
  };
  ejecutarAtajoRef.current = ejecutarAtajo;

  /**
   * Pegar una URL de imagen sobre un Referente (o con uno seleccionado) añade un
   * medio que apunta a esa fuente con la fecha del día. No descarga la imagen.
   */
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
      const archivos = Array.from(event.clipboardData?.files ?? []);
      if (!archivos.length) {
        for (const item of Array.from(event.clipboardData?.items ?? [])) {
          if (item.kind !== 'file') continue;
          const file = item.getAsFile();
          if (file) archivos.push(file);
        }
      }
      const punto = puntoDePegado();
      const seleccionUnica = selectedCardIds.length === 1 ? selectedCardIds[0] : null;
      const referenteDestino = (() => {
        if (!activeBoard) return undefined;
        const id = hoveredReferenteId.current ?? seleccionUnica;
        return id ? activeBoard.cards.find((item) => item.id === id && item.type === 'referente') : undefined;
      })();
      if (archivos.length && activeBoard) {
        event.preventDefault();
        if (referenteDestino) {
          adjuntarRef.current(referenteDestino.id, archivos);
          return;
        }
        const medios = archivos.filter((file) => file.type.startsWith('image/') || file.type.startsWith('video/'));
        medios.forEach((file, indice) => {
          void addMediaRef.current(file, { x: punto.x + indice * 36, y: punto.y + indice * 28 });
        });
        return;
      }
      const text = event.clipboardData?.getData('text/plain').trim() ?? '';
      // Copia interna: la marca va primero; si el sistema trae texto o imagen, mandan ellos.
      if ((esMarcaDeTarjetas(text) || (!text && hayTarjetasCopiadas())) && pegarSeleccion()) {
        event.preventDefault();
        return;
      }
      if (!text || !activeBoard) return;
      if (isSafeExternalUrl(text)) {
        if (referenteDestino) {
          event.preventDefault();
          void capturarUrlEnReferente(referenteDestino.id, text);
          return;
        }
        // Sin referente debajo: la URL pegada nace como enlace en el cursor.
        event.preventDefault();
        const creada = addToolCard('link', (nueva) => {
          nueva.url = text;
          nueva.title = text;
        }, punto);
        if (!creada) return;
        setNotice('Enlace pegado. Buscando título, descripción e imagen…');
        void aplicarVistaPrevia(creada.id, text);
        return;
      }
      // Texto plano: nace una nota con el texto en el punto del cursor (A-1 · D9).
      event.preventDefault();
      const primeraLinea = text.split(/\r?\n/).map((linea) => linea.trim()).find(Boolean)?.slice(0, 60);
      const creada = addToolCard('note', (nueva) => {
        nueva.title = primeraLinea || 'Nota pegada';
        nueva.body = text.slice(0, 12000);
      }, punto);
      if (creada) setNotice('Texto pegado como nota en el cursor.');
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [activeBoard, addToolCard, aplicarVistaPrevia, capturarUrlEnReferente, pegarSeleccion, selectedCardIds]);

  const onCardSelect = useCallback((card: BoardCard, event: Modificadores) => cardHandlers.current?.select(card.id, event), []);
  const onCardConnect = useCallback((cardId: string) => cardHandlers.current?.connect(cardId), []);
  const onCardConnectStart = useCallback((card: BoardCard, event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.connectStart(card, event), []);
  const onCardDragStart = useCallback((card: BoardCard, event: React.PointerEvent<HTMLElement>, force?: boolean) => cardHandlers.current?.dragStart(card, event, force), []);
  const onCardDragMove = useCallback((event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.dragMove(event), []);
  const onCardDragEnd = useCallback((event: React.PointerEvent<HTMLElement>) => cardHandlers.current?.dragEnd(event), []);
  const onCardDelete = useCallback((cardId: string) => cardHandlers.current?.delete(cardId), []);
  const onCardPatch = useCallback((cardId: string, patch: Partial<BoardCard>) => cardHandlers.current?.patch(cardId, patch), []);
  const onCardReplace = useCallback((card: BoardCard) => cardHandlers.current?.replace(card), []);
  const onCardHover = useCallback((cardId: string, over: boolean) => cardHandlers.current?.hover(cardId, over), []);
  const onCardBlur = useCallback(() => cardHandlers.current?.blur(), []);

  cardHandlers.current = {
    select: handleCardSelection,
    connect: handleConnectCard,
    connectStart: iniciarConector,
    dragStart: startCardDrag,
    dragMove: moveCardDrag,
    dragEnd: endCardDrag,
    delete: removeCard,
    patch: updateCard,
    replace: replaceCard,
    hover: (cardId, over) => {
      if (over) hoveredReferenteId.current = cardId;
      else if (hoveredReferenteId.current === cardId) hoveredReferenteId.current = null;
    },
    blur: closeTextGroup,
  };

  const matchingCards = useMemo(() => {
    const inicio = marca('busqueda:filtro', `consulta de ${search.trim().length} caracteres`);
    const query = search.trim().toLocaleLowerCase();
    const coincidencias = new Set((activeBoard?.cards ?? []).filter((card) => !query || `${card.title} ${card.body} ${card.url ?? ''}`.toLocaleLowerCase().includes(query)).map((card) => card.id));
    marcaFin('busqueda:filtro:fin', inicio, `${coincidencias.size} de ${activeBoard?.cards.length ?? 0}`);
    return coincidencias;
  }, [activeBoard?.cards, search]);

  const resultadosBusqueda = useMemo(() => {
    const inicio = marca('busqueda:resultados', searchScope);
    const query = search.trim();
    const vacio: Array<{ boardId: string; boardTitle: string; card: BoardCard }> = [];
    if (!query) {
      marcaFin('busqueda:resultados:fin', inicio, '0');
      return vacio;
    }
    const fuentes = searchScope === 'tablero'
      ? (activeBoard ? [activeBoard] : [])
      : projectBoards.length ? projectBoards : activeBoard ? [activeBoard] : [];
    const vistos = new Set<string>();
    const resultados: Array<{ boardId: string; boardTitle: string; card: BoardCard }> = [];
    for (const board of fuentes) {
      for (const card of board.cards) {
        if (searchScope === 'biblioteca' && !(card.type === 'referente' || board.title.toLocaleLowerCase().includes('biblioteca'))) continue;
        if (!coincideBusqueda(card, query)) continue;
        const clave = `${board.id}:${card.id}`;
        if (vistos.has(clave)) continue;
        vistos.add(clave);
        resultados.push({ boardId: board.id, boardTitle: board.title, card });
        if (resultados.length >= 200) {
          marcaFin('busqueda:resultados:fin', inicio, '200 (tope)');
          return resultados;
        }
      }
    }
    marcaFin('busqueda:resultados:fin', inicio, `${resultados.length}`);
    return resultados;
  }, [activeBoard, projectBoards, search, searchScope]);

  useEffect(() => {
    setSearchActivo(0);
  }, [search, searchScope]);

  const indiceOrdenado = useMemo(() => ordenDePintado(activeBoard?.cards ?? []), [activeBoard?.cards]);
  const indiceFiltrado = useMemo(() => {
    const inicio = marca('indice:filtro', `consulta de ${indexQuery.trim().length} caracteres`);
    const filtrado = indiceOrdenado.filter((card) => coincideBusqueda(card, indexQuery));
    marcaFin('indice:filtro:fin', inicio, `${filtrado.length} de ${indiceOrdenado.length}`);
    return filtrado;
  }, [indiceOrdenado, indexQuery]);
  const ventanaIndice = ventanaVirtual(indiceFiltrado.length, indexScroll, 420, INDICE_ROW_HEIGHT);
  const indiceVisibles = indiceFiltrado.slice(ventanaIndice.inicio, ventanaIndice.fin);

  useEffect(() => {
    if (!indexOpen) return;
    const frame = requestAnimationFrame(() => indexSearchRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [indexOpen]);

  const cerrarIndice = useCallback((devolverFoco = true) => {
    marca('indice:cerrar', `${indiceFiltrado.length} filas`);
    setIndexOpen(false);
    setIndexQuery('');
    setIndexScroll(0);
    if (devolverFoco) viewportRef.current?.focus({ preventScroll: true });
  }, [indiceFiltrado.length]);

  const abrirIndice = useCallback(() => {
    marca('indice:abrir', `${activeBoard?.cards.length ?? 0} tarjetas`);
    setIndexOpen(true);
    setIndexQuery('');
    setIndexScroll(0);
  }, [activeBoard?.cards.length]);

  /** ⌘F · Enter lleva al resultado: cambia de tablero si hace falta, selecciona y centra. */
  const centrarEnTarjeta = useCallback((boardId: string, cardId: string) => {
    const board = boardsRef.current.find((item) => item.id === boardId);
    if (!board) return;
    if (activeBoard?.id !== boardId) {
      pendingCentro.current = { boardId, cardId };
      setActiveBoardId(boardId);
      setSelectedCardIds([]);
      setSearch('');
      return;
    }
    const card = board.cards.find((item) => item.id === cardId);
    if (!card) return;
    const contenedor = board.cards.find((item) => {
      if (item.type !== 'marco') return false;
      const data = readFrameData(item);
      return data.vista !== 'libre' && data.hijos.includes(card.id);
    });
    const objetivo = contenedor ?? card;
    const medida = measureCardSizes().get(objetivo.id);
    const ancho = medida?.width ?? objetivo.width;
    const alto = medida?.height ?? objetivo.height ?? (objetivo.type === 'marco' ? readFrameData(objetivo).alto : 210);
    const zoom = Math.max(0.55, Math.min(1.4, cameraRef.current.zoom));
    cameraRef.current = {
      zoom,
      pan: {
        x: viewportSize.width / 2 - (objetivo.x + ancho / 2) * zoom,
        y: viewportSize.height / 2 - (objetivo.y + alto / 2) * zoom,
      },
    };
    setSelectedCardIds([objetivo.id]);
    setSearch('');
    aplicarCamara();
    sincronizarCamara();
    viewportRef.current?.focus({ preventScroll: true });
  }, [activeBoard?.id, aplicarCamara, measureCardSizes, sincronizarCamara, viewportSize.height, viewportSize.width]);

  useEffect(() => {
    const pendiente = pendingCentro.current;
    if (!pendiente || !activeBoard || activeBoard.id !== pendiente.boardId) return;
    pendingCentro.current = null;
    const timer = window.setTimeout(() => centrarEnTarjeta(pendiente.boardId, pendiente.cardId), 80);
    return () => window.clearTimeout(timer);
  }, [activeBoard, centrarEnTarjeta]);

  const seleccionarDesdeIndice = (card: BoardCard, event: React.MouseEvent) => {
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => alternarEnSeleccion(current, card.id));
    } else {
      setSelectedCardIds([card.id]);
    }
  };

  if (!loaded) {
    return <div className="board-loading" role="status">Abriendo tu tablero…</div>;
  }
  if (!activeBoard) {
    return (
      <div className="board-loading board-no-project-board">
        <div role="status">{projectError ?? 'Este proyecto todavía no tiene un tablero.'}</div>
        <button className="board-tool primary" onClick={() => void addNewBoard()}><Plus size={15} /> Crear tablero</button>
        <button className="board-tool" onClick={onBack}>Volver a PDF Studio</button>
      </div>
    );
  }

  return (
    <div className={`board-workspace densidad-${ajustes.densidad}`} inert={locked || undefined}>
      <header className="board-header" data-testid="board-topbar">
        <button className="board-back" onClick={() => void leaveBoard()} title="Volver al espacio PDF" aria-label="Volver a PDF Studio">
          <ArrowLeft size={16} aria-hidden="true" />
        </button>
        <div className="board-identity">
          <span className="board-mark" aria-hidden="true">P</span>
          {renamingProject && activeProject ? (
            <input
              className="board-project-rename"
              value={projectDraft}
              autoFocus
              maxLength={120}
              aria-label="Nombre del proyecto"
              onChange={(event) => setProjectDraft(event.target.value)}
              onBlur={() => { void commitProjectRename(); }}
              onKeyDown={(event) => {
                event.stopPropagation();
                if (event.key === 'Enter') {
                  event.preventDefault();
                  event.currentTarget.blur();
                } else if (event.key === 'Escape') {
                  event.preventDefault();
                  setProjectDraft(activeProject.name);
                  setRenamingProject(false);
                }
              }}
            />
          ) : (
            <>
              <label className="sr-only" htmlFor="project-select">Proyecto</label>
              <select
                id="project-select"
                className="board-project-select"
                value={activeProjectId}
                onChange={(event) => { void handleProjectSelect(event.target.value); }}
                onDoubleClick={(event) => {
                  if (!activeProject) return;
                  event.preventDefault();
                  setProjectDraft(activeProject.name);
                  setRenamingProject(true);
                }}
                aria-label="Elegir proyecto"
                title="Doble clic para renombrar el proyecto"
                disabled={!projectOptions.length}
              >
                {projectOptions.length ? projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>) : <option value="">Proyectos no disponibles</option>}
              </select>
              <div className="board-menu-wrap" ref={projectMenuRef}>
                <button
                  type="button"
                  className="board-icon-button"
                  onClick={() => setProjectMenuOpen((open) => !open)}
                  aria-haspopup="menu"
                  aria-expanded={projectMenuOpen}
                  aria-label="Menú del proyecto"
                  title="Menú del proyecto"
                ><MoreHorizontal size={16} /></button>
                {projectMenuOpen && (
                  <div className="board-menu" role="menu" aria-label="Proyecto">
                    <button type="button" role="menuitem" onClick={() => { setProjectMenuOpen(false); if (activeProject) { setProjectDraft(activeProject.name); setRenamingProject(true); } }} disabled={!activeProject}>Renombrar (F2)</button>
                    <button type="button" role="menuitem" onClick={() => { setProjectMenuOpen(false); setMoveTargetId(projectOptions.find((project) => project.id !== activeProjectId)?.id ?? ''); setMoveDialog(true); }} disabled={!activeBoard || projectOptions.length < 2}>Mover tablero a otro proyecto…</button>
                    <button type="button" role="menuitem" onClick={() => { setProjectMenuOpen(false); void archivarProyecto(); }} disabled={!activeProject}>Archivar proyecto</button>
                    <button type="button" role="menuitem" onClick={() => { setProjectMenuOpen(false); void abrirArchivo(); }}>Borrar definitivamente… (Archivo)</button>
                  </div>
                )}
              </div>
            </>
          )}
          <span className="board-identity-separator" aria-hidden="true">·</span>
          <label className="sr-only" htmlFor="board-select">Tablero</label>
          <select id="board-select" className="board-board-select" value={activeBoard.id} onChange={(event) => {
            // El select es controlado: hay que guardar el destino antes del await,
            // porque mientras se guarda vuelve a pintar el tablero actual.
            const destino = event.target.value;
            void (async () => {
              const saved = await flushBoardWrites();
              if (!saved) {
                setNotice('No se cambió de tablero porque el actual aún no se pudo guardar. Reintenta o exporta una copia.');
                return;
              }
              setActiveBoardId(destino);
              setSelectedCardIds([]);
            })();
          }} aria-label="Elegir tablero">
            {projectBoards.map((board) => <option key={board.id} value={board.id}>{board.title || 'Sin título'}</option>)}
          </select>
          <label className="sr-only" htmlFor="design-system-select">Sistema de diseño del tablero</label>
          <select
            id="design-system-select"
            className="board-system-select"
            value={normalizeDesignSystem(activeBoard.sistema)}
            onChange={(event) => {
              const sistema = normalizeDesignSystem(event.target.value) as DesignSystemId;
              updateBoard((board) => ({ ...board, sistema }));
            }}
            aria-label="Sistema de diseño del tablero"
            title="Sistema de diseño de este tablero"
          >
            {DESIGN_SYSTEMS.map((entry) => <option key={entry.id} value={entry.id}>{entry.nombre}</option>)}
          </select>
          <button className="board-icon-button" onClick={() => { const nombre = window.prompt('Nombre del tablero', activeBoard.title); if (nombre !== null) renameBoard(nombre.trim() || activeBoard.title); }} aria-label="Renombrar tablero" title="Renombrar tablero"><Pencil size={15} /></button>
          <button className="board-icon-button" onClick={() => { setProjectName(''); setProjectDialog(true); }} aria-label="Crear proyecto" title="Crear proyecto"><FolderPlus size={16} /></button>
          <button className="board-icon-button" onClick={() => void addNewBoard()} aria-label="Crear tablero" title="Crear tablero"><Plus size={16} /></button>
          <button className="board-icon-button" onClick={abrirPlantillas} aria-label="Plantillas de tablero" title="Crear un tablero desde una plantilla"><LayoutTemplate size={15} /></button>
          <button className="board-icon-button" onClick={() => importInput.current?.click()} aria-label="Importar tablero" title="Importar tablero desde JSON o Markdown"><Upload size={15} /></button>
          <button className="board-icon-button danger" onClick={() => void removeCurrentBoard()} aria-label="Eliminar tablero" title="Eliminar tablero"><Trash2 size={15} /></button>
          <span className={`board-save-state ${saveState}`} aria-live="polite">
            {saveState === 'saving' ? 'Guardando…' : saveState === 'error' ? 'Sin guardar' : 'Guardado'}
          </span>
        </div>

        <div className="board-topbar-search">
          <Search size={14} aria-hidden="true" />
          <input
            ref={searchInputRef}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault();
                setSearchActivo((actual) => Math.min(Math.max(0, resultadosBusqueda.length - 1), actual + 1));
              } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setSearchActivo((actual) => Math.max(0, actual - 1));
              } else if (event.key === 'Enter') {
                const resultado = resultadosBusqueda[searchActivo] ?? resultadosBusqueda[0];
                if (resultado) {
                  event.preventDefault();
                  centrarEnTarjeta(resultado.boardId, resultado.card.id);
                }
              } else if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                setSearch('');
                viewportRef.current?.focus({ preventScroll: true });
              }
            }}
            placeholder="Buscar en el tablero"
            aria-label="Buscar tarjetas"
            aria-expanded={Boolean(search.trim())}
          />
          {search && <button type="button" onClick={() => setSearch('')} aria-label="Limpiar búsqueda"><X size={13} /></button>}
          {search.trim() && (
            <div className="board-search-results" role="listbox" aria-label="Resultados de búsqueda">
              <div className="board-search-results-head">
                <strong aria-live="polite" data-testid="search-count">{resultadosBusqueda.length} {resultadosBusqueda.length === 1 ? 'resultado' : 'resultados'}</strong>
                <label>
                  Alcance
                  <select value={searchScope} onChange={(event) => setSearchScope(event.target.value as 'tablero' | 'proyecto' | 'biblioteca')} aria-label="Alcance de búsqueda">
                    <option value="tablero">Tablero</option>
                    <option value="proyecto">Proyecto</option>
                    <option value="biblioteca">Biblioteca</option>
                  </select>
                </label>
              </div>
              {resultadosBusqueda.length === 0 ? (
                <p className="board-search-empty">Nada coincide. Prueba otro término o alcance.</p>
              ) : (
                <ul>
                  {resultadosBusqueda.slice(0, 40).map((resultado, indice) => (
                    <li key={`${resultado.boardId}:${resultado.card.id}`}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={indice === searchActivo}
                        className={indice === searchActivo ? 'is-active' : ''}
                        onMouseEnter={() => setSearchActivo(indice)}
                        onClick={() => centrarEnTarjeta(resultado.boardId, resultado.card.id)}
                      >
                        <span className="board-search-result-title">{resultado.card.title || 'Sin título'}</span>
                        <span className="board-search-result-meta">{resultado.card.type} · {resultado.boardTitle}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="board-search-hint">Enter salta al primero · ↑↓ recorre · Esc vuelve al lienzo</p>
            </div>
          )}
        </div>

        <div className="board-topbar-actions">
          <button className="board-icon-button" onClick={undo} disabled={!canUndo} title="Deshacer (⌘/Ctrl + Z)" aria-label="Deshacer"><Undo2 size={16} /></button>
          <button className="board-icon-button" onClick={redo} disabled={!canRedo} title="Rehacer (⌘/Ctrl + Shift + Z)" aria-label="Rehacer"><Redo2 size={16} /></button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button
            type="button"
            className={`board-icon-button ${handMode ? 'active' : ''}`}
            onClick={() => setHandMode((value) => !value)}
            aria-pressed={handMode}
            aria-label={handMode ? 'Mano activa: mover el lienzo' : 'Mano: mover el lienzo con un dedo'}
            title={handMode ? 'Mano activa · un dedo mueve el lienzo' : 'Mano · un dedo mueve el lienzo'}
          ><Hand size={16} /></button>
          <button className={`board-icon-button ${connectMode ? 'active' : ''}`} onClick={() => { setConnectMode((value) => !value); setConnectFromId(null); setNotice(connectMode ? null : 'Elige una tarjeta y luego otra para conectarlas.'); }} aria-pressed={connectMode} title="Relacionar tarjetas" aria-label="Relacionar tarjetas"><Link2 size={16} /></button>
          <button className={`board-icon-button ${snapEnabled ? 'active' : ''}`} onClick={() => updateAjustes({ iman: !ajustes.iman })} aria-pressed={snapEnabled} title="Imán y cuadrícula de este tablero" aria-label="Imán y cuadrícula"><Magnet size={16} /></button>
          <button className={`board-icon-button ${boardSettingsOpen ? 'active' : ''}`} onClick={() => setBoardSettingsOpen((open) => !open)} aria-pressed={boardSettingsOpen} title="Este tablero: guías, fondo, cursor y densidad" aria-label="Ajustes de este tablero"><SlidersHorizontal size={16} /></button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button className="board-icon-button" onClick={() => zoomBy(1 / 1.15)} aria-label="Alejar" title="Alejar"><ZoomOut size={16} /></button>
          <button ref={zoomValueRef} className="board-zoom-value" onClick={fitBoard} title="Ajustar el tablero a la pantalla" aria-label={`Zoom ${Math.round(zoom * 100)} por ciento, ajustar tablero`}>{Math.round(zoom * 100)}%</button>
          <button className="board-icon-button" onClick={() => zoomBy(1.15)} aria-label="Acercar" title="Acercar"><ZoomIn size={16} /></button>

          <button
            type="button"
            className="board-icon-button board-help-button"
            onClick={() => setShortcutsOpen(true)}
            aria-label="Atajos de teclado"
            title="Atajos de teclado (?)"
          >?</button>

          <div className="board-menu-wrap" ref={exportMenuRef}>
            <button type="button" className="board-bar-button" onClick={() => { setExportMenuOpen((open) => !open); setLibraryMenuOpen(false); }} aria-haspopup="menu" aria-expanded={exportMenuOpen} title="Exportar y publicar">
              <Download size={15} /> Exportar <ChevronDown size={14} />
            </button>
            {exportMenuOpen && (
              <div className="board-menu" role="menu" aria-label="Exportar">
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportJson(); }}>JSON del tablero</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportMarkdown(); }}>Markdown</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportProjectMarkdown(); }} disabled={!activeProject}>Obsidian del proyecto</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); exportReferentesObsidian(); }}>Referentes a Obsidian</button>
                <button type="button" role="menuitem" onClick={() => { setExportMenuOpen(false); publicarSeleccion(); }}>Publicar marco seleccionado</button>
              </div>
            )}
          </div>

          <div className="board-menu-wrap" ref={libraryMenuRef}>
            <button type="button" className="board-bar-button" onClick={() => { setLibraryMenuOpen((open) => !open); setExportMenuOpen(false); }} aria-haspopup="menu" aria-expanded={libraryMenuOpen} title="Biblioteca y rituales">
              <Library size={15} /> Biblioteca <ChevronDown size={14} />
            </button>
            {libraryMenuOpen && (
              <div className="board-menu" role="menu" aria-label="Biblioteca">
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setMirarOpen(true); }}>Volver a mirar</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); void crearManifiesto(); }} disabled={manifesting}>{manifesting ? 'Escribiendo…' : 'Manifiesto de la semana'}</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); void importReferentes(); }}>Importar referentes</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); gustosInput.current?.click(); }}>Importar gustos</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setPdfReferenceDialog(true); }} disabled={!activeProject || !pdfReferenceSource}>Referenciar página PDF</button>
                <button type="button" role="menuitem" onClick={() => { setLibraryMenuOpen(false); setReferencesOpen(true); }} disabled={!activeProjectReferences.length}>Referencias PDF ({activeProjectReferences.length})</button>
              </div>
            )}
          </div>

          <button
            type="button"
            className="board-icon-button"
            onClick={() => (indexOpen ? cerrarIndice(true) : abrirIndice())}
            aria-label="Índice del tablero"
            title="Índice del tablero (L)"
          ><List size={16} /></button>
          <button
            type="button"
            className="board-icon-button"
            onClick={() => void abrirArchivo()}
            aria-label="Archivo y recientes borrados"
            title="Archivo · recientes borrados (30 días)"
          ><Archive size={16} /></button>
        </div>
      </header>

      {engineMessage && <div className="board-engine-notice" role="status"><span>{engineMessage}</span>{onRetryEngine && <button className="board-tool" onClick={onRetryEngine}>Reintentar motor PDF</button>}</div>}
      {projectError && <div className="board-alert" role="alert"><span>{projectError} Tus tableros locales siguen disponibles.</span><button type="button" onClick={() => { loadedProjectBoardSignature.current = ''; setProjectError(null); setProjectLoadAttempt((value) => value + 1); }}>Reintentar proyectos</button><button type="button" onClick={() => setProjectError(null)} aria-label="Cerrar aviso"><X size={14} /></button></div>}
      {storageError && (
        <div className="board-alert" role="alert">
          <span>{storageError}. Tus cambios siguen en esta ventana.</span>
          {writes.error && <button type="button" onClick={() => void flushBoardWrites()}>Reintentar guardado</button>}
          <button type="button" onClick={exportJson}>Exportar copia de rescate</button>
          <button type="button" onClick={() => setLoadError(null)} aria-label="Cerrar aviso"><X size={14} /></button>
        </div>
      )}
      {notice && <div className="board-toast" role="status">{notice}<button onClick={() => setNotice(null)} aria-label="Cerrar aviso"><X size={14} /></button></div>}
      {aviso && (
        <div className="board-toast board-undo-toast" role="status" data-testid="board-undo-toast">
          <span>{aviso.texto}</span>
          {(aviso.historial || aviso.deshacer) && (
            <button
              type="button"
              className="board-undo-action"
              onClick={() => {
                const deshacer = aviso.historial ? undo : aviso.deshacer;
                setAviso(null);
                deshacer?.();
              }}
            >Deshacer</button>
          )}
          <button type="button" onClick={() => setAviso(null)} aria-label="Cerrar aviso"><X size={14} /></button>
        </div>
      )}
      {referencesOpen && activeProject && (
        <aside className="board-reference-panel" aria-label={`Referencias PDF de ${activeProject.name}`}>
          <div className="board-reference-heading"><div><strong>Referencias PDF</strong><span>{activeProject.name}</span></div><button className="board-icon-button" onClick={() => setReferencesOpen(false)} aria-label="Cerrar referencias"><X size={15} /></button></div>
          {activeProjectReferences.map((reference) => (
            <article className="board-reference-card" key={reference.id}>
              <strong>{reference.sourceName}</strong>
              <span>Página {reference.page}</span>
              {reference.quote && <blockquote>{reference.quote}</blockquote>}
              {reference.note && <p>{reference.note}</p>}
              <small>SHA-256 · {reference.sourceSha256.slice(0, 12)}…</small>
              <div className="board-reference-actions"><button className="board-tool" onClick={() => handleOpenPdfReference(reference)}>Abrir página</button><button className="board-tool danger" onClick={() => void handleDeletePdfReference(reference)}>Eliminar</button></div>
            </article>
          ))}
        </aside>
      )}

      {indexOpen && activeBoard && (
        <aside className="board-index-panel" aria-label="Índice del tablero">
          <div className="board-index-head">
            <div>
              <strong>Índice</strong>
              <span>{indiceFiltrado.length} de {activeBoard.cards.length} · arriba se pinta encima</span>
            </div>
            <button type="button" className="board-icon-button" onClick={() => cerrarIndice(true)} aria-label="Cerrar índice"><X size={15} /></button>
          </div>
          <input
            ref={indexSearchRef}
            className="board-index-search"
            value={indexQuery}
            onChange={(event) => { setIndexQuery(event.target.value); setIndexScroll(0); }}
            placeholder="Buscar en el índice"
            aria-label="Buscar en el índice"
          />
          <div className="board-index-tools">
            <span aria-live="polite">{selectedCardIds.length} {selectedCardIds.length === 1 ? 'seleccionada' : 'seleccionadas'}</span>
            <button type="button" className="board-tool" onClick={() => ordenarSeleccion('frente')} disabled={!selectedCardIds.length}>Traer al frente</button>
          </div>
          <div
            className="board-index-list"
            style={{ height: 420 }}
            onScroll={(event) => setIndexScroll(event.currentTarget.scrollTop)}
            role="listbox"
            aria-label="Tarjetas en orden de pintado"
            aria-multiselectable="true"
          >
            <div style={{ paddingTop: ventanaIndice.offsetSuperior, paddingBottom: ventanaIndice.offsetInferior }}>
              {indiceVisibles.map((card) => (
                <div
                  key={card.id}
                  className={`board-index-row ${selectedCardIds.includes(card.id) ? 'selected' : ''}`}
                  style={{ height: INDICE_ROW_HEIGHT }}
                  role="option"
                  aria-selected={selectedCardIds.includes(card.id)}
                  tabIndex={0}
                  onClick={(event) => seleccionarDesdeIndice(card, event)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      seleccionarDesdeIndice(card, event as unknown as React.MouseEvent);
                    }
                  }}
                >
                  <span className="board-index-title">{card.title || 'Sin título'}</span>
                  <span className="board-index-meta">{card.type}{card.locked ? ' · bloqueada' : ''}</span>
                  <button
                    type="button"
                    className="board-index-lock"
                    onPointerDown={(event) => event.stopPropagation()}
                    onClick={(event) => { event.stopPropagation(); updateCard(card.id, { locked: !card.locked }); }}
                    aria-label={card.locked ? `Desbloquear ${card.title || 'tarjeta'}` : `Bloquear ${card.title || 'tarjeta'}`}
                  >{card.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
                </div>
              ))}
            </div>
          </div>
          <p className="board-index-foot">El índice es una lista, no un panel de capas: se abre con L y Esc vuelve al lienzo.</p>
        </aside>
      )}

      <div className="board-body">
        <aside className="board-rail" aria-label="Herramientas del tablero">
          {RAIL_TOOLS.map((toolId) => {
            const tool = getBoardTool(toolId);
            if (!tool) return null;
            const Icono = tool.icono;
            const etiquetas: Record<string, string> = { note: 'Nota', link: 'Enlace', media: 'Imagen', tareas: 'Tareas', columna: 'Columna', referente: 'Referente', marco: 'Marco', entropia: 'Entropía' };
            const aria: Record<string, string> = { note: 'Nueva nota', link: 'Añadir enlace', media: 'Añadir imagen', tareas: 'Nueva lista de tareas', columna: 'Nueva columna', referente: 'Añadir referente', marco: 'Dibujar marco', entropia: 'Añadir entropía' };
            return (
              <button
                key={toolId}
                type="button"
                className={`board-rail-tool ${toolId === 'note' ? 'primary' : ''} ${frameToolId === toolId ? 'active' : ''}`}
                onClick={() => activarHerramienta(toolId)}
                draggable
                onDragStart={startToolDrag(toolId)}
                aria-label={aria[toolId] ?? tool.nombre}
                title={`${etiquetas[toolId] ?? tool.nombre} · arrastra al tablero`}
              >
                {Icono ? <Icono size={19} /> : <Plus size={18} />}
                <span>{etiquetas[toolId] ?? tool.nombre}</span>
              </button>
            );
          })}
          <button type="button" className="board-rail-tool" onClick={() => {
            if (!addMenuOpen) addPointRef.current = lastPointerWorld.current ?? screenToWorld({ x: viewportSize.width / 2, y: viewportSize.height / 2 }, cameraRef.current);
            setAddMenuOpen((open) => !open);
          }} aria-haspopup="menu" aria-expanded={addMenuOpen} aria-label="Más herramientas" title="Más herramientas del registro">
            <Plus size={19} />
            <span>Más</span>
          </button>
        </aside>

      <main
        ref={viewportRef}
        tabIndex={0}
        aria-label="Lienzo del tablero"
        className={`board-viewport ${isPanning ? 'panning' : ''} ${spacePanActive ? 'space-pan' : ''} ${handMode ? 'hand-mode' : ''} ${connectMode ? 'connecting' : ''} ${frameToolId ? 'drawing-frame' : ''} cursor-${ajustes.cursor} textura-${ajustes.textura} densidad-${ajustes.densidad} ${ajustes.reticula ? 'con-reticula' : 'sin-reticula'}`}
        style={{ backgroundColor: ajustes.fondo }}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          if (event.key !== 'Tab' || event.shiftKey) return;
          const tarjetas = viewportRef.current?.querySelectorAll<HTMLElement>('[data-card-id]');
          if (!tarjetas?.length) return;
          event.preventDefault();
          const preferida = selectedCardIds.length
            ? viewportRef.current?.querySelector<HTMLElement>(`[data-card-id="${CSS.escape(selectedCardIds[0])}"]`)
            : null;
          (preferida ?? tarjetas[0]).focus();
        }}
        onPointerDown={beginViewportGesture}
        onPointerMove={moveViewportGesture}
        onPointerUp={endViewportGesture}
        onPointerCancel={endViewportGesture}
        onDragOver={(event) => {
          if (event.dataTransfer.types.includes('application/x-prometeo-tool') || event.dataTransfer.types.includes('Files')) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
          }
        }}
        onDrop={dropTool}
        onClickCapture={(event) => {
          if (!suppressViewportClick.current) return;
          suppressViewportClick.current = false;
          event.stopPropagation();
          event.preventDefault();
        }}
        onClick={(event) => {
          if (event.target === viewportRef.current) setSelectedCardIds([]);
        }}
      >
        <svg className="board-relations" width={viewportSize.width} height={viewportSize.height} viewBox={`0 0 ${Math.max(1, viewportSize.width)} ${Math.max(1, viewportSize.height)}`} aria-label="Relaciones entre tarjetas">
            <defs><marker id="board-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" /></marker></defs>
            <g ref={relationsRef}>
            {activeBoard.relations.map((relation) => {
              const from = activeBoard.cards.find((card) => card.id === relation.from);
              const to = activeBoard.cards.find((card) => card.id === relation.to);
              if (!from || !to) return null;
              const geo = geometriaConector(rectDeTarjeta(from), rectDeTarjeta(to));
              return (
                <g key={relation.id} className={`board-relation tone-${relation.tone ?? 'ember'}`}>
                  <path
                    className="board-relation-path"
                    d={geo.path}
                    markerEnd="url(#board-arrow)"
                    onDoubleClick={(event) => { event.stopPropagation(); editarEtiquetaRelacion(relation); }}
                  >
                    <title>{relation.label || 'Doble clic para etiquetar el conector'}</title>
                  </path>
                  {relation.label && (
                    <text className="board-relation-label" x={geo.medio.x} y={geo.medio.y} textAnchor="middle" dominantBaseline="middle" onDoubleClick={(event) => { event.stopPropagation(); editarEtiquetaRelacion(relation); }}>
                      {relation.label}
                    </text>
                  )}
                </g>
              );
            })}
            {connectDraft && (() => {
              const desde = activeBoard.cards.find((card) => card.id === connectDraft.from);
              if (!desde) return null;
              const geo = geometriaConector(rectDeTarjeta(desde), { x: connectDraft.mundo.x, y: connectDraft.mundo.y, width: 1, height: 1 });
              return <path className={`board-relation-draft ${connectDraft.target ? 'has-target' : ''}`} d={geo.path} />;
            })()}
            </g>
          </svg>
        <div className={`board-stage ${hasNegative ? 'has-negative' : ''}`} ref={stageRef}>
          {ajustes.guias !== 'apagadas' && guias.x !== undefined && (
            <div className={`board-guide board-guide-x guias-${ajustes.guias}`} data-testid="board-guide-x" style={{ left: guias.x }} aria-hidden="true" />
          )}
          {ajustes.guias !== 'apagadas' && guias.y !== undefined && (
            <div className={`board-guide board-guide-y guias-${ajustes.guias}`} data-testid="board-guide-y" style={{ top: guias.y }} aria-hidden="true" />
          )}
          {activeBoard.cards.map((card) => {
            const matches = matchingCards.has(card.id);
            if (card.type === 'columna') {
              const hijos = readColumnData(card).hijos
                .map((id) => cardsById.get(id))
                .filter((item): item is BoardCard => Boolean(item));
              return (
                <BoardColumn
                  key={card.id}
                  card={card}
                  childrenCards={hijos}
                  selected={selectedCardIds.includes(card.id)}
                  dimmed={!matches}
                  dragging={draggingIds.includes(card.id)}
                  settling={settlingIds.includes(card.id)}
                  dropTarget={dropFrameId === card.id}
                  onSelect={onCardSelect}
                  onDragStart={onCardDragStart}
                  onDragMove={onCardDragMove}
                  onDragEnd={onCardDragEnd}
                  onDelete={onCardDelete}
                  onPatch={onCardPatch}
                  onSettings={abrirAjustesTarjeta}
                  onToggleFold={(id) => updateBoard((board) => ({ ...board, cards: setColumnFolded(board.cards, id, !readColumnData(card).plegada) }))}
                  onReorderChild={(columnId, childId, targetId) => updateBoard((board) => ({ ...board, cards: reordenarHijoDeColumna(board.cards, columnId, childId, targetId) }))}
                  onDetachChild={(columnId, childId) => updateBoard((board) => ({ ...board, cards: quitarHijoDeColumna(board.cards, columnId, childId) }))}
                  onResizeStart={startFrameResize}
                  onResizeMove={moveFrameResize}
                  onResizeEnd={endFrameResize}
                />
              );
            }
            if (card.type === 'marco') {
              const frame = readFrameData(card);
              const childCount = frame.hijos.filter((id) => cardsById.has(id)).length;
              const esEntropia = esMarcoEntropia(card);
              const collage = esEntropia ? leerEntropia(card) : null;
              return (
                <article
                  key={card.id}
                  data-card-id={card.id}
                  data-marco={esEntropia ? 'entropia' : 'libre'}
                  tabIndex={-1}
                  aria-selected={selectedCardIds.includes(card.id)}
                  aria-label={`Marco: ${card.title || 'sin título'}`}
                  className={`board-frame ${esEntropia ? 'is-entropia' : ''} ${collage?.guardado ? 'is-guardado' : ''} ${frame.vista === 'archivo' ? 'is-archive' : frame.vista === 'muro' ? 'is-muro' : frame.vista === 'mesa' ? 'is-mesa' : ''} ${selectedCardIds.includes(card.id) ? 'selected' : ''} ${!matches ? 'dimmed' : ''} ${draggingIds.includes(card.id) ? 'dragging' : ''} ${settlingIds.includes(card.id) ? 'settling' : ''} ${dropFrameId === card.id ? 'drop-target' : ''} ${card.locked ? 'is-locked' : ''}`}
                  style={{ left: card.x, top: card.y, width: card.width, height: frame.alto }}
                  onPointerMove={moveCardDrag}
                  onPointerUp={endCardDrag}
                  onPointerCancel={endCardDrag}
                  onClick={(event) => handleCardSelection(card.id, event)}
                  onDoubleClick={(event) => {
                    if (frame.vista !== 'archivo') return;
                    const target = event.target as HTMLElement;
                    if (target.closest('input,select,a')) return;
                    const control = target.closest('button');
                    if (control && !control.classList.contains('archivo-zone')) return;
                    event.stopPropagation();
                    setArchiveFullscreenId(card.id);
                  }}
                  onBlurCapture={onCardBlur}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleCardSelection(card.id, event);
                    }
                  }}
                >
                  <div className="board-frame-head" onPointerDown={(event) => startCardDrag(card, event)} onPointerMove={moveCardDrag} onPointerUp={endCardDrag} onPointerCancel={endCardDrag} title="Arrastra para mover el marco y sus tarjetas">
                    <span className="board-drag-grip" aria-hidden="true">⠿</span>
                    <TituloEnSitio value={card.title} onCommit={(title) => updateCard(card.id, { title })} ariaLabel="Título del marco" className="board-frame-title" />
                    {!esEntropia && (
                      <label className="board-frame-view">
                        Ver como
                        <select value={frame.vista} onChange={(event) => updateFrameView(card.id, event.target.value as FrameView)} aria-label={`Ver como: ${card.title || 'marco'}`}>
                          <option value="libre">Libre</option>
                          <option value="archivo">Archivo</option>
                          <option value="muro">Muro</option>
                          <option value="mesa">Mesa de luz</option>
                        </select>
                      </label>
                    )}
                    {!esEntropia && (
                      <button
                        className="board-frame-publish"
                        type="button"
                        disabled={publishingFrameId === card.id}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => { event.stopPropagation(); void publishFrame(card); }}
                        title="Publicar esta vista como web local (index.html + style.css + media/)"
                        aria-label={`Publicar ${card.title || 'marco'}`}
                      >{publishingFrameId === card.id ? '…' : 'Publicar'}</button>
                    )}
                    {selectedCardIds.includes(card.id) && (
                      <button
                        type="button"
                        className="board-frame-settings"
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => { event.stopPropagation(); abrirAjustesTarjeta(card, event); }}
                        aria-label={`Ajustes de ${card.title || 'el marco'}`}
                        title="Ajustes de este marco"
                      ><SlidersHorizontal size={13} /></button>
                    )}
                    <button
                      type="button"
                      className="board-frame-lock"
                      onPointerDown={(event) => event.stopPropagation()}
                      onClick={(event) => { event.stopPropagation(); updateCard(card.id, { locked: !card.locked }); }}
                      aria-label={card.locked ? 'Desbloquear marco' : 'Bloquear marco'}
                      title={card.locked ? 'Desbloquear' : 'Bloquear posición, tamaño y borrado'}
                    >{card.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
                    <button className="board-frame-delete" disabled={card.locked} onClick={(event) => { event.stopPropagation(); removeCard(card.id); }} aria-label="Eliminar marco" title="Eliminar el marco y dejar sus tarjetas"><X size={14} /></button>
                  </div>
                  {esEntropia ? (
                    <EntropiaVista
                      datos={collage}
                      fuentes={fuentesEntropia}
                      onTirar={() => tirarEnMarcoEntropia(card)}
                      onOtra={() => tirarEnMarcoEntropia(card, nuevaSemilla())}
                      onLike={() => guardarCollageEntropia(card)}
                      onNope={() => descartarCollageEntropia(card)}
                    />
                  ) : frame.vista === 'archivo' ? (
                    <>
                      <ArchivoView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} />
                      <div className="board-frame-hint">Doble clic en el proyecto: pliego · en el encabezado: pantalla completa</div>
                    </>
                  ) : frame.vista === 'muro' ? (
                    <>
                      <MuroView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                      <div className="board-frame-hint">Clic en una miniatura: caja de luz · ← → recorren</div>
                    </>
                  ) : frame.vista === 'mesa' ? (
                    <MesaView frameTitle={card.title} cards={activeBoard.cards} childIds={frame.hijos} width={Math.max(180, card.width)} />
                  ) : (
                    <div className="board-frame-meta">{childCount} {childCount === 1 ? 'tarjeta' : 'tarjetas'} dentro</div>
                  )}
                  {!card.locked && DIRECCIONES_ASA.map((direccion) => (
                    <button
                      key={direccion}
                      type="button"
                      className={`board-frame-resize ${direccion}`}
                      onPointerDown={(event) => startFrameResize(card, direccion, event)}
                      onPointerMove={moveFrameResize}
                      onPointerUp={endFrameResize}
                      onPointerCancel={endFrameResize}
                      aria-label={`Redimensionar ${card.title || 'marco'} desde ${direccion}`}
                      title="Redimensionar marco"
                    />
                  ))}
                </article>
              );
            }
            // Los hijos de un marco con vista propia se pintan dentro del marco, no encima.
            if (framedChildIds.has(card.id)) return null;
            if (esMediaLibre(card)) {
              return (
                <BoardFreeMedia
                  key={card.id}
                  card={card}
                  selected={selectedCardIds.includes(card.id)}
                  dimmed={!matches}
                  dragging={draggingIds.includes(card.id)}
                  settling={settlingIds.includes(card.id)}
                  onSelect={onCardSelect}
                  onDragStart={onCardDragStart}
                  onDragMove={onCardDragMove}
                  onDragEnd={onCardDragEnd}
                   onDelete={onCardDelete}
                   onPatch={onCardPatch}
                   onSettings={abrirAjustesTarjeta}
                   onResizeStart={startFreeResize}
                  onResizeMove={moveFreeResize}
                  onResizeEnd={endFreeResize}
                  onNaturalSize={ajustarAlturaNatural}
                  onReplaceMedia={(cardId, file) => void reemplazarMedia(cardId, file)}
                />
              );
            }
            return (
              <BoardCardItem
                key={card.id}
                card={card}
                selected={selectedCardIds.includes(card.id)}
                dimmed={!matches}
                dragging={draggingIds.includes(card.id)}
                settling={settlingIds.includes(card.id)}
                 connectionSource={connectFromId === card.id}
                 connectionTarget={connectDraft?.target === card.id}
                 connectMode={connectMode}
                 colors={COLORS}
                 compact={!lodCompletas.has(card.id)}
                 onSelect={onCardSelect}
                 onConnect={onCardConnect}
                 onConnectStart={onCardConnectStart}
                 onDragStart={onCardDragStart}
                 onDragMove={onCardDragMove}
                 onDragEnd={onCardDragEnd}
                 onWidthResizeStart={startWidthResize}
                 onWidthResizeMove={moveWidthResize}
                 onWidthResizeEnd={endWidthResize}
                 onDelete={onCardDelete}
                 onSettings={abrirAjustesTarjeta}
                 onPatch={onCardPatch}
                 onReplace={onCardReplace}
                 onHover={onCardHover}
                 onBlurCapture={onCardBlur}
                 acciones={accionesHerramientas}
              />
            );
          })}
          {propuestaManifiesto && (
            <div
              className="board-propuesta"
              style={{
                left: propuestaManifiesto.frame.x,
                top: propuestaManifiesto.frame.y,
                width: propuestaManifiesto.frame.width,
                height: readFrameData(propuestaManifiesto.frame).alto,
              }}
              role="group"
              aria-label="Propuesta de manifiesto pendiente"
              onClick={(event) => { event.stopPropagation(); aceptarManifiesto(); }}
            >
              <div className="board-propuesta-head">Propuesta de la IA · Enter o clic acepta · Esc descarta</div>
              <h3>{propuestaManifiesto.frame.title || 'Manifiesto'}</h3>
              <div className="board-propuesta-lines">
                {propuestaManifiesto.cards.slice(0, 12).map((card) => <p key={card.id}>{card.title || card.body}</p>)}
              </div>
            </div>
          )}
          {frameDraft && (
            <div
              className="board-frame-draft"
              style={{ left: frameDraft.x, top: frameDraft.y, width: frameDraft.width, height: frameDraft.height }}
              aria-hidden="true"
            />
          )}
          {activeBoard.cards.length === 0 && (
            <div className="board-empty" style={{ left: (viewportSize.width / 2 - pan.x) / zoom - 170, top: (viewportSize.height / 2 - pan.y) / zoom - 60 }}>
              <strong>Tu espacio de ideas está listo</strong>
              <span>Agrega una nota, enlace o archivo para empezar.</span>
              <button onClick={() => addToolCard('note')}><Plus size={14} /> Crear primera nota</button>
            </div>
          )}
        </div>

        {marquee && (
          <div
            className="board-marquee"
            data-testid="board-marquee"
            style={{ left: marquee.x, top: marquee.y, width: marquee.width, height: marquee.height }}
            aria-hidden="true"
          />
        )}

        <div className="board-count">
          {activeBoard.cards.length} {activeBoard.cards.length === 1 ? 'tarjeta' : 'tarjetas'} · arrastra el fondo para seleccionar · Espacio + arrastra para mover · ⌘/Ctrl + rueda para acercar
          <span data-testid="history-status" className="board-history-status" aria-live="polite">
            {historyStatus === 'nueva' ? ' · sesión nueva' : ' · historial restaurado'}
          </span>
        </div>
        <div className="sr-only" aria-live="polite" aria-atomic="true" data-testid="selection-live">
          {selectedCardIds.length === 0
            ? 'Sin selección'
            : `${selectedCardIds.length} ${selectedCardIds.length === 1 ? 'seleccionada' : 'seleccionadas'}`}
        </div>
      </main>

        <input ref={importInput} type="file" accept="application/json,.json,text/markdown,.md" hidden onChange={(event) => { void importBoard(event.target.files?.[0]); event.target.value = ''; }} />
        <input ref={mediaInput} type="file" accept="image/*,video/*,audio/*,application/pdf,text/plain,.txt" hidden onChange={(event) => {
          const punto = mediaPointRef.current ?? undefined;
          mediaPointRef.current = null;
          void addMedia(event.target.files?.[0], punto);
          event.target.value = '';
        }} />
        <input ref={gustosInput} type="file" accept="application/json,.json" hidden aria-label="Archivo de gustos parciales" onChange={(event) => { void importGustos(event.target.files?.[0]); event.target.value = ''; }} />
      </div>

      {archiveFullscreenFrame && (
        <div ref={(element) => { dialogRef.current = element; }} className="board-archive-fullscreen" role="dialog" aria-modal="true" aria-label={`Archivo a pantalla completa: ${archiveFullscreenFrame.title || 'marco'}`}>
          <button type="button" className="archivo-fullscreen-close" onClick={() => setArchiveFullscreenId(null)}>Esc · volver a la pizarra</button>
          <ArchivoView
            frameTitle={archiveFullscreenFrame.title}
            cards={activeBoard.cards}
            childIds={readFrameData(archiveFullscreenFrame).hijos}
            fullscreen
          />
        </div>
      )}

      {selectedCards.length > 1 && (
        <div className="board-selection-bar" role="toolbar" aria-label={`Alinear ${selectedCards.length} tarjetas seleccionadas`}>
          <span className="board-selection-count">{selectedCards.length} seleccionadas</span>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('left')} aria-label="Alinear a la izquierda" title="Alinear a la izquierda">Izq</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('center-x')} aria-label="Centrar en vertical" title="Alinear los centros sobre el eje vertical">Centro</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('right')} aria-label="Alinear a la derecha" title="Alinear a la derecha">Der</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('top')} aria-label="Alinear arriba" title="Alinear arriba">Arriba</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('center-y')} aria-label="Centrar en horizontal" title="Alinear los centros sobre el eje horizontal">Medio</button>
          <button type="button" className="board-selection-button" onClick={() => alignSelection('bottom')} aria-label="Alinear abajo" title="Alinear abajo">Abajo</button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button type="button" className="board-selection-button" onClick={() => distributeSelection('horizontal')} disabled={selectedCardIds.length < 3} aria-label="Distribuir horizontalmente" title="Distribuir con espacios iguales en horizontal">↔</button>
          <button type="button" className="board-selection-button" onClick={() => distributeSelection('vertical')} disabled={selectedCardIds.length < 3} aria-label="Distribuir verticalmente" title="Distribuir con espacios iguales en vertical">↕</button>
          <span className="board-tool-divider" aria-hidden="true" />
          <button type="button" className="board-selection-button danger" onClick={deleteSelectedCards} aria-label="Eliminar tarjetas seleccionadas" title="Eliminar tarjetas seleccionadas"><Trash2 size={14} /></button>
        </div>
      )}

      {mirarOpen && (
        <MirarDialog
          boards={boards}
          activeBoardId={activeBoard.id}
          tableroNombre={activeBoard.title}
          proyecto={activeProject?.name || 'Proyecto general'}
          onClose={() => setMirarOpen(false)}
          onAceptar={aceptarLecturaEnReferente}
        />
      )}

      {archiveOpen && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setArchiveOpen(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide board-archive-dialog" role="dialog" aria-modal="true" aria-labelledby="board-archive-title">
            <div className="board-dialog-heading">
              <h2 id="board-archive-title">Archivo</h2>
              <button type="button" onClick={() => setArchiveOpen(false)} aria-label="Cerrar Archivo"><X size={16} /></button>
            </div>
            <p className="board-dialog-hint">Lo que borras no desaparece del todo: queda aquí durante 30 días, sin papelera permanente.</p>
            <section className="board-archive-section" aria-labelledby="board-archive-recents">
              <div className="board-archive-section-head">
                <h3 id="board-archive-recents"><History size={15} aria-hidden="true" /> Recientes borrados</h3>
                <span>{borrados.length} {borrados.length === 1 ? 'entrada' : 'entradas'}</span>
              </div>
              {archiveError && <p className="board-dialog-error" role="alert">{archiveError}</p>}
              {borrados.length === 0 ? (
                <p className="board-archive-empty">Todavía no hay nada borrado en los últimos 30 días.</p>
              ) : (
                <ul className="board-archive-list" aria-label="Recientes borrados">
                  {borrados.map((entry) => {
                    const dias = Math.max(0, Math.ceil((Date.parse(entry.expiresAt) - Date.now()) / (24 * 60 * 60 * 1000)));
                    return (
                      <li key={entry.id} className="board-archive-item" data-borrado-kind={entry.kind} data-borrado-id={entry.id}>
                        <span className="board-archive-kind">{ETIQUETA_BORRADO[entry.kind]}</span>
                        <div className="board-archive-copy">
                          <strong>{entry.label}</strong>
                          <small>{new Date(entry.deletedAt).toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' })} · quedan {dias} días</small>
                        </div>
                        <button type="button" className="board-tool primary" disabled={restoringId === entry.id} onClick={() => void restaurarEntrada(entry)}>
                          {restoringId === entry.id ? 'Restaurando…' : 'Restaurar'}
                        </button>
                        <button type="button" className="board-tool danger" onClick={() => void olvidarEntrada(entry.id)} aria-label={`Olvidar ${entry.label} para siempre`}>Olvidar</button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
            <section className="board-archive-section" aria-labelledby="board-archive-projects">
              <div className="board-archive-section-head">
                <h3 id="board-archive-projects">Proyectos archivados</h3>
                <span>{archivedProjects.length}</span>
              </div>
              {archivedProjects.length === 0 ? (
                <p className="board-archive-empty">No hay proyectos archivados.</p>
              ) : (
                <ul className="board-archive-list">
                  {archivedProjects.map((project) => (
                    <li key={project.id} className="board-archive-item">
                      <span className="board-archive-kind">Proyecto</span>
                      <div className="board-archive-copy"><strong>{project.name}</strong><small>Fuera del selector; sus datos siguen guardados.</small></div>
                      <button type="button" className="board-tool primary" onClick={() => void restaurarProyecto(project.id)}>Restaurar</button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="board-archive-section" aria-labelledby="board-archive-delete">
              <div className="board-archive-section-head">
                <h3 id="board-archive-delete">Borrar definitivamente</h3>
              </div>
              <p className="board-dialog-hint">Solo desde Archivo y escribiendo el nombre. El proyecto, sus tableros y vínculos quedan 30 días en la memoria.</p>
              <label className="board-archive-delete-label">
                Proyecto
                <select
                  value={deleteProjectId ?? ''}
                  onChange={(event) => { setDeleteProjectId(event.target.value || null); setDeleteProjectDraft(''); setArchiveError(null); }}
                  aria-label="Proyecto a borrar definitivamente"
                >
                  <option value="">Elige un proyecto</option>
                  {projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </label>
              {deleteProjectId && (() => {
                const project = projects.find((item) => item.id === deleteProjectId);
                if (!project) return null;
                return (
                  <div className="board-archive-delete-confirm">
                    <input
                      value={deleteProjectDraft}
                      onChange={(event) => setDeleteProjectDraft(event.target.value)}
                      placeholder={`Escribe «${project.name}»`}
                      aria-label="Nombre del proyecto para confirmar el borrado"
                    />
                    <button type="button" className="board-tool danger" onClick={() => void borrarProyectoDefinitivo(project.id)}>Borrar definitivamente</button>
                  </div>
                );
              })()}
            </section>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool primary" onClick={() => setArchiveOpen(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {boardSettingsOpen && (
        <aside className="board-settings-panel" aria-label="Este tablero" role="dialog">
          <div className="board-settings-head">
            <div><strong>Este tablero</strong><span>Se guarda con este tablero, no con la app.</span></div>
            <button type="button" className="board-icon-button" onClick={() => setBoardSettingsOpen(false)} aria-label="Cerrar ajustes del tablero"><X size={15} /></button>
          </div>
          <div className="board-settings-body">
            <label>Guías de alineación
              <select value={ajustes.guias} onChange={(event) => updateAjustes({ guias: event.target.value as BoardSettings['guias'] })}>
                <option value="visibles">Visibles</option>
                <option value="sutiles">Sutiles (casi invisibles)</option>
                <option value="apagadas">Apagadas</option>
              </select>
            </label>
            <label className="board-settings-check"><input type="checkbox" checked={ajustes.iman} onChange={(event) => updateAjustes({ iman: event.target.checked })} /> Imán y ajuste a la cuadrícula</label>
            <label className="board-settings-check"><input type="checkbox" checked={ajustes.reticula} onChange={(event) => updateAjustes({ reticula: event.target.checked })} /> Retícula del fondo</label>
            <label>Color del fondo
              <span className="board-settings-color">
                <input type="color" value={ajustes.fondo} onChange={(event) => updateAjustes({ fondo: event.target.value })} aria-label="Color del fondo del tablero" />
                <code>{ajustes.fondo}</code>
              </span>
            </label>
            <label>Textura
              <select value={ajustes.textura} onChange={(event) => updateAjustes({ textura: event.target.value as BoardSettings['textura'] })}>
                <option value="ninguna">Ninguna</option>
                <option value="puntos">Puntos</option>
                <option value="papel">Papel</option>
                <option value="lino">Lino</option>
              </select>
            </label>
            <label>Cursor sobre el lienzo
              <select value={ajustes.cursor} onChange={(event) => updateAjustes({ cursor: event.target.value as BoardSettings['cursor'] })}>
                <option value="normal">Normal</option>
                <option value="cruz">Cruz</option>
                <option value="mano">Mano</option>
              </select>
            </label>
            <label>Densidad de controles
              <select value={ajustes.densidad} onChange={(event) => updateAjustes({ densidad: event.target.value as BoardSettings['densidad'] })}>
                <option value="compacta">Compacta</option>
                <option value="normal">Normal</option>
                <option value="amplia">Amplia</option>
              </select>
            </label>
            <p className="board-settings-hint">Las guías solo aparecen mientras arrastras y solo cuando hay un ajuste real.</p>
          </div>
        </aside>
      )}

      {settingsCardId && settingsPos && (() => {
        const card = activeBoard?.cards.find((item) => item.id === settingsCardId);
        if (!card) return null;
        const estilo = card.estilo ?? {};
        const varias = idsDeAjustes.length > 1;
        const recorte = leerRecorte(card);
        const alt = typeof card.datos?.alt === 'string' ? card.datos.alt : '';
        const aplicarAlt = (valor: string) => {
          const ids = new Set(idsDeAjustes);
          updateBoard((board) => ({
            ...board,
            cards: board.cards.map((item) => (ids.has(item.id) ? { ...item, datos: { ...item.datos, alt: valor.slice(0, 300) } } : item)),
          }), { coalesceKey: 'alt-medios' });
        };
        const aplicarRecorte = (patch: Partial<typeof recorte>) => {
          const ids = new Set(idsDeAjustes);
          updateBoard((board) => ({
            ...board,
            cards: board.cards.map((item) => (ids.has(item.id) && item.type === 'media'
              ? { ...item, datos: { ...item.datos, recorte: { ...leerRecorte(item), ...patch } } }
              : item)),
          }), { coalesceKey: 'recorte-medios' });
        };
        return (
          <div className="board-card-settings-panel" style={{ left: settingsPos.x, top: settingsPos.y }} role="dialog" aria-label="Ajustes de la tarjeta" onPointerDown={(event) => event.stopPropagation()}>
            <div className="board-card-settings-head">
              <div><strong>{varias ? `${idsDeAjustes.length} tarjetas` : card.title || 'Tarjeta'}</strong><span>{varias ? 'Los cambios se aplican a toda la selección.' : 'Se aplica en vivo, sin Aplicar.'}</span></div>
              <button type="button" className="board-icon-button" onClick={() => setSettingsCardId(null)} aria-label="Cerrar ajustes de la tarjeta"><X size={14} /></button>
            </div>
            <div className="board-card-settings-body">
              <fieldset>
                <legend>Color</legend>
                <div className="board-card-settings-colors">
                  {COLORS.map((color) => (
                    <button key={color} type="button" className={`board-settings-swatch color-${color} ${card.color === color ? 'current' : ''}`} onClick={() => aplicarColor(color)} aria-label={`Color ${color}`} aria-pressed={card.color === color} />
                  ))}
                </div>
              </fieldset>
              <label>Tipografía
                <select value={estilo.fontFamily ?? ''} onChange={(event) => aplicarEstilo({ fontFamily: event.target.value || undefined })}>
                  <option value="">La del tablero</option>
                  <option value="Georgia, serif">Georgia</option>
                  <option value="Palatino, serif">Palatino</option>
                  <option value="Helvetica, Arial, sans-serif">Helvetica</option>
                  <option value="Avenir Next, Avenir, sans-serif">Avenir</option>
                  <option value="Menlo, monospace">Menlo</option>
                  <option value="Courier New, monospace">Courier</option>
                </select>
              </label>
              <label>Tamaño de texto <output>{estilo.fontSize ?? 16} px</output>
                <input type="range" min="10" max="40" step="1" value={estilo.fontSize ?? 16} onChange={(event) => aplicarEstilo({ fontSize: Number(event.target.value) })} />
              </label>
              <label>Color del texto <input type="color" value={estilo.textColor ?? '#2b2118'} onChange={(event) => aplicarEstilo({ textColor: event.target.value })} /></label>
              <div className="board-card-settings-row">
                <label>Borde <input type="range" min="0" max="6" step="0.5" value={estilo.borderWidth ?? 0} onChange={(event) => aplicarEstilo({ borderWidth: Number(event.target.value), borderColor: estilo.borderColor ?? '#8a6a4a', borderStyle: estilo.borderStyle && estilo.borderStyle !== 'none' ? estilo.borderStyle : 'solid' })} /></label>
                <label>Estilo
                  <select value={estilo.borderStyle ?? 'solid'} onChange={(event) => aplicarEstilo({ borderStyle: event.target.value as NonNullable<BoardCard['estilo']>['borderStyle'], borderWidth: estilo.borderWidth ?? 1, borderColor: estilo.borderColor ?? '#8a6a4a' })}>
                    <option value="solid">Sólido</option>
                    <option value="dashed">Discontinuo</option>
                    <option value="none">Sin borde</option>
                  </select>
                </label>
              </div>
              <div className="board-card-settings-row">
                <label>Sombra
                  <select value={estilo.shadow ?? 'suave'} onChange={(event) => aplicarEstilo({ shadow: event.target.value as NonNullable<BoardCard['estilo']>['shadow'] })}>
                    <option value="none">Sin sombra</option>
                    <option value="suave">Suave</option>
                    <option value="fuerte">Fuerte</option>
                  </select>
                </label>
                <label>Opacidad <output>{Math.round((estilo.opacity ?? 1) * 100)}%</output>
                  <input type="range" min="0.1" max="1" step="0.05" value={estilo.opacity ?? 1} onChange={(event) => aplicarEstilo({ opacity: Number(event.target.value) })} />
                </label>
              </div>
              <label className="board-settings-check"><input type="checkbox" checked={card.locked} onChange={alternarBloqueoSeleccion} /> Bloqueada (no se mueve ni se borra)</label>
              <label>Convertir en
                <select value={card.type === 'note' || card.type === 'marco' || card.type === 'columna' ? card.type : 'note'} onChange={(event) => convertirEn(event.target.value as 'note' | 'marco' | 'columna')}>
                  <option value="note">Nota</option>
                  <option value="columna">Columna</option>
                  <option value="marco">Marco</option>
                </select>
              </label>
              {card.type === 'media' && (
                <>
                  <div className="board-card-settings-row">
                    <label>Recorte X <output>{Math.round(recorte.x * 100)}%</output>
                      <input type="range" min="0" max="1" step="0.02" value={recorte.x} onChange={(event) => aplicarRecorte({ x: Number(event.target.value) })} />
                    </label>
                    <label>Recorte Y <output>{Math.round(recorte.y * 100)}%</output>
                      <input type="range" min="0" max="1" step="0.02" value={recorte.y} onChange={(event) => aplicarRecorte({ y: Number(event.target.value) })} />
                    </label>
                  </div>
                  <label>Zoom del recorte <output>{recorte.escala.toFixed(2)}×</output>
                    <input type="range" min="1" max="3" step="0.05" value={recorte.escala} onChange={(event) => aplicarRecorte({ escala: Number(event.target.value) })} />
                  </label>
                  <label>Texto alternativo<input value={alt} maxLength={300} onChange={(event) => aplicarAlt(event.target.value)} placeholder="Qué se ve en la imagen" /></label>
                </>
              )}
            </div>
          </div>
        );
      })()}

      {shortcutsOpen && (
        <div className="board-add-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShortcutsOpen(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-shortcuts" role="dialog" aria-modal="true" aria-labelledby="board-shortcuts-title">
            <div className="board-dialog-heading">
              <h2 id="board-shortcuts-title">Atajos del tablero</h2>
              <button type="button" onClick={() => setShortcutsOpen(false)} aria-label="Cerrar atajos"><X size={16} /></button>
            </div>
            <p className="board-dialog-hint">Los mismos gestos que ves en los controles, sin tener que buscarlos.</p>
            <div className="board-shortcuts-groups">
              {gruposDeAyuda().map((group) => (
                <section className="board-shortcuts-group" key={group.grupo} aria-label={group.grupo}>
                  <h3>{group.grupo}</h3>
                  <dl>
                    {group.items.map((atajo) => (
                      <div className="board-shortcut" key={atajo.id}>
                        <dt><kbd>{textoAtajo(atajo)}</kbd></dt>
                        <dd>{atajo.descripcion}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool primary" onClick={() => setShortcutsOpen(false)}>Entendido</button>
            </div>
          </div>
        </div>
      )}

      {addMenuOpen && (
        <div
          className="board-add-backdrop"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setAddMenuOpen(false); }}
          onDragOver={(event) => {
            if (event.dataTransfer.types.includes('application/x-prometeo-tool') || event.dataTransfer.types.includes('Files')) {
              event.preventDefault();
              event.dataTransfer.dropEffect = 'copy';
            }
          }}
          onDrop={(event) => {
            const toolId = event.dataTransfer.getData('application/x-prometeo-tool');
            if (!toolId) return;
            event.preventDefault();
            setAddMenuOpen(false);
            const rect = viewportRef.current?.getBoundingClientRect();
            if (!rect) return;
            const punto = screenToWorld({ x: event.clientX - rect.left, y: event.clientY - rect.top }, cameraRef.current);
            addToolCard(toolId, undefined, punto);
          }}
        >
          <div className="board-add-panel" role="presentation">
            <div className="board-add-heading">
              <span>Biblioteca de herramientas</span>
              <button type="button" onClick={() => setAddMenuOpen(false)} aria-label="Cerrar menú"><X size={15} /></button>
            </div>
            <BoardToolMenu onChoose={chooseTool} />
          </div>
        </div>
      )}

      {nestedDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setNestedDialog(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide" role="dialog" aria-modal="true" aria-labelledby="board-nested-title">
            <div className="board-dialog-heading"><h2 id="board-nested-title">Anidar un tablero</h2><button type="button" onClick={() => setNestedDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">La tarjeta guarda solo el vínculo. Al abrirla cambias de tablero sin perder lo que estabas mirando.</p>
            <div className="board-template-grid">
              {projectBoards.map((board) => (
                <button key={board.id} type="button" className="board-template-card" onClick={() => crearTableroAnidado(board)}>
                  <strong>{board.title || 'Sin título'}</strong>
                  <span>{board.cards.length} {board.cards.length === 1 ? 'tarjeta' : 'tarjetas'}</span>
                </button>
              ))}
            </div>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setNestedDialog(false)}>Cancelar</button></div>
          </div>
        </div>
      )}

      {templateDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setTemplateDialog(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog board-dialog-wide" role="dialog" aria-modal="true" aria-labelledby="board-template-title">
            <div className="board-dialog-heading"><h2 id="board-template-title">Plantillas de tablero</h2><button type="button" onClick={() => setTemplateDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">Crear una plantilla no copia archivos: solo la estructura de tarjetas, columnas y tareas.</p>
            <div className="board-template-grid">
              {templates.map((plantilla) => (
                <div key={plantilla.id} className="board-template-card-wrap">
                  <button type="button" className="board-template-card" onClick={() => { void aplicarPlantilla(plantilla); }}>
                    <strong>{plantilla.nombre}</strong>
                    <span>{plantilla.descripcion}</span>
                    <small>{plantilla.builtin ? 'Incluida' : 'Guardada por ti'}</small>
                  </button>
                  {!plantilla.builtin && (
                    <button type="button" className="board-template-delete" onClick={() => borrarPlantillaGuardada(plantilla.id)} aria-label={`Eliminar plantilla ${plantilla.nombre}`} title="Eliminar plantilla guardada"><Trash2 size={12} /></button>
                  )}
                </div>
              ))}
            </div>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool" onClick={guardarTableroComoPlantilla} disabled={!activeBoard}>Guardar este tablero como plantilla</button>
              <button type="button" className="board-tool primary" onClick={() => setTemplateDialog(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {linkDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLinkDialog(false); }}>
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="board-link-title" onSubmit={saveLinkCard}>
            <div className="board-dialog-heading"><h2 id="board-link-title">Añadir enlace</h2><button type="button" onClick={() => setLinkDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <label>Título<input autoFocus value={linkTitle} onChange={(event) => setLinkTitle(event.target.value)} placeholder="Nombre de la referencia" /></label>
            <label>Dirección web<input type="url" required value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="https://…" /></label>
            {linkError && <p className="board-dialog-error" role="alert">{linkError}</p>}
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setLinkDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Agregar enlace</button></div>
          </form>
        </div>
      )}

      {moveDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setMoveDialog(false); }}>
          <div ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="board-move-title">
            <div className="board-dialog-heading"><h2 id="board-move-title">Mover tablero a otro proyecto</h2><button type="button" onClick={() => setMoveDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">El tablero conserva sus tarjetas, referencias y memoria de gusto. No se copia: cambia de proyecto.</p>
            <label>Proyecto destino
              <select value={moveTargetId} onChange={(event) => setMoveTargetId(event.target.value)} aria-label="Proyecto destino">
                <option value="">Elige un proyecto</option>
                {projectOptions.filter((project) => project.id !== activeProjectId).map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>
            <div className="board-dialog-actions">
              <button type="button" className="board-tool" onClick={() => setMoveDialog(false)}>Cancelar</button>
              <button type="button" className="board-tool primary" onClick={() => void moverTableroAProyecto()} disabled={!moveTargetId}>Mover tablero</button>
            </div>
          </div>
        </div>
      )}

      {projectDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setProjectDialog(false); }}>
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" onSubmit={(event) => { void handleCreateProject(event); }}>
            <div className="board-dialog-heading"><h2 id="project-dialog-title">Crear proyecto</h2><button type="button" onClick={() => setProjectDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">Agrupa tableros y referencias PDF. Los archivos originales permanecen en su ubicación.</p>
            <label>Nombre del proyecto<input autoFocus required maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Por ejemplo, Investigación" /></label>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setProjectDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Crear proyecto</button></div>
          </form>
        </div>
      )}

      {pdfReferenceDialog && (
        <div className="board-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setPdfReferenceDialog(false); }}>
          <form ref={(element) => { dialogRef.current = element; }} className="board-dialog" role="dialog" aria-modal="true" aria-labelledby="pdf-reference-title" onSubmit={(event) => { void handleSavePdfReference(event); }}>
            <div className="board-dialog-heading"><h2 id="pdf-reference-title">Referenciar página PDF</h2><button type="button" onClick={() => setPdfReferenceDialog(false)} aria-label="Cerrar"><X size={16} /></button></div>
            <p className="board-dialog-hint">{pdfReferenceSource?.filename ?? 'Sin PDF abierto'} · página {pdfReferenceSource?.page ?? '—'}</p>
            <p className="board-dialog-hint">Se guarda el nombre, página y huella del PDF, junto con tu nota. El PDF no se copia.</p>
            <label>Cita o fragmento<textarea maxLength={2000} value={pdfReferenceQuote} onChange={(event) => setPdfReferenceQuote(event.target.value)} rows={4} placeholder="Fragmento que quieres recordar" /></label>
            <label>Nota<textarea maxLength={3000} value={pdfReferenceNote} onChange={(event) => setPdfReferenceNote(event.target.value)} rows={4} placeholder="Por qué es importante para el proyecto" /></label>
            <div className="board-dialog-actions"><button type="button" className="board-tool" onClick={() => setPdfReferenceDialog(false)}>Cancelar</button><button type="submit" className="board-tool primary">Guardar referencia</button></div>
          </form>
        </div>
      )}
    </div>
  );
};
