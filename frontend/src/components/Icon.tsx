import type { LucideIcon, LucideProps } from "lucide-react";
import {
    AlertCircle, ArrowLeftRight, ArrowRightLeft, Award, BadgeCheck, BarChart3,
    Building2, Calendar, CheckCircle2, CheckSquare, CircleUser, CloudUpload, Copy,
    Database, DollarSign, Download, FileSpreadsheet, FileText, FileUp, Folder, Gauge,
    Globe, IndianRupee, Info, Layers, Link, List, LogOut, MapPin, MessageSquareText,
    Moon, Network, NotebookText, Package, Pencil, Plus, PlusCircle, Receipt,
    ReceiptText, RefreshCw, ScanBarcode, ShieldCheck, Square, SquarePen, Star, Sun,
    Table, Tags, ToggleRight, Trash2, TrendingUp, TriangleAlert, User, UserPlus,
    Users,
} from "lucide-react";

/**
 * Maps legacy Bootstrap-Icons class names to lucide-react components.
 *
 * The Bootstrap icon font was removed in the Tailwind migration, so any
 * `<i className="bi bi-*">` renders blank. Components/config that still carry
 * Bootstrap icon-name strings render them through <Icon name="…"> instead.
 */
const BI_TO_LUCIDE: Record<string, LucideIcon> = {
    "arrow-left-right": ArrowLeftRight,
    "arrow-repeat": RefreshCw,
    "award": Award,
    "badge-tm": BadgeCheck,
    "bar-chart-line": BarChart3,
    "box-arrow-in-down": Download,
    "box-arrow-right": LogOut,
    "box-seam": Package,
    "building": Building2,
    "calendar3": Calendar,
    "chat-left-text": MessageSquareText,
    "check-circle": CheckCircle2,
    "check2-circle": CheckCircle2,
    "check2-square": CheckSquare,
    "cloud-upload": CloudUpload,
    "copy": Copy,
    "currency-dollar": DollarSign,
    "currency-exchange": ArrowRightLeft,
    "currency-rupee": IndianRupee,
    "database": Database,
    "diagram-3": Network,
    "download": Download,
    "exclamation-circle": AlertCircle,
    "exclamation-triangle": TriangleAlert,
    "exclamation-triangle-fill": TriangleAlert,
    "file-earmark-arrow-up": FileUp,
    "file-earmark-excel": FileSpreadsheet,
    "file-earmark-text": FileText,
    "file-pdf": FileText,
    "folder": Folder,
    "geo-alt": MapPin,
    "graph-up-arrow": TrendingUp,
    "info-circle": Info,
    "intersect": Layers,
    "journal-text": NotebookText,
    "link-45deg": Link,
    "list-ul": List,
    "pencil": Pencil,
    "pencil-fill": Pencil,
    "pencil-square": SquarePen,
    "people": Users,
    "person": User,
    "person-circle": CircleUser,
    "person-plus": UserPlus,
    "plus-circle": PlusCircle,
    "plus-circle-fill": PlusCircle,
    "plus-lg": Plus,
    "receipt": Receipt,
    "receipt-cutoff": ReceiptText,
    "shield-lock": ShieldCheck,
    "speedometer2": Gauge,
    "star": Star,
    "table": Table,
    "tags": Tags,
    "toggle-on": ToggleRight,
    "trash": Trash2,
    "trophy": Award,
    "upc-scan": ScanBarcode,
    "x-lg": Square,
    "sun": Sun,
    "moon": Moon,
};

interface IconProps extends Omit<LucideProps, "ref"> {
    /** Bootstrap-Icons name, with or without a leading `bi-` (e.g. "plus-lg"). */
    name?: string;
}

/** Renders the lucide equivalent of a legacy Bootstrap icon name. */
export default function Icon({ name, className = "size-4", ...rest }: IconProps) {
    const key = (name || "").replace(/^bi-/, "");
    const Cmp = BI_TO_LUCIDE[key] || Square;
    return <Cmp className={className} aria-hidden="true" {...rest} />;
}
