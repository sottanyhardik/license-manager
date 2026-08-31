import api from "../api/axios";
import { relativeApiUrl } from "./licenseLedgerExport";

export type PackageLicence = {
    id: number | string;
    license_id?: number | string;
    licence_number: string;
    status: string;
    completed_at?: string | null;
    download_url?: string | null;
    filename?: string;
    size?: number | null;
    sha256?: string | null;
    error?: string | null;
};

export type DownloadState = {
    jobId: string;
    directory?: FileSystemDirectoryHandle;
    queued: string[];
    downloading: string | null;
    downloaded: string[];
    failed: string[];
    expected: Record<string, { filename: string; size: number; sha256: string }>;
    directoryAuthorized?: boolean;
    /** Display names only: browsers intentionally do not reveal an absolute path. */
    selectedDirectoryName?: string;
    jobDirectoryName?: string;
};

// The File System Access declarations are not available in every installed DOM
// library yet.  Keep the narrow shape we actually use here.
export type FileSystemWritable = { write(data: Blob): Promise<void>; close(): Promise<void>; abort?(): Promise<void> };
export type FileSystemFileHandle = { getFile(): Promise<File>; createWritable(): Promise<FileSystemWritable> };
export type FileSystemDirectoryHandle = {
    name?: string;
    getDirectoryHandle(name: string, options?: { create?: boolean }): Promise<FileSystemDirectoryHandle>;
    getFileHandle(name: string, options?: { create?: boolean }): Promise<FileSystemFileHandle>;
    queryPermission?(descriptor?: { mode?: "read" | "readwrite" }): Promise<PermissionState>;
    requestPermission?(descriptor?: { mode?: "read" | "readwrite" }): Promise<PermissionState>;
};

declare global {
    interface Window { showDirectoryPicker?: (options: { mode: "readwrite" }) => Promise<FileSystemDirectoryHandle>; }
}

const DB = "license-ledger-package-downloads";
const STORE = "jobs";

function safeFilename(value: string): string {
    const clean = value.replace(/[^A-Za-z0-9._-]/g, "_");
    if (!clean || clean !== value || !clean.endsWith(".pdf")) throw new Error("The server returned an unsafe PDF filename.");
    return clean;
}

function itemKey(item: PackageLicence): string { return String(item.license_id ?? item.id); }

async function openDb(): Promise<IDBDatabase | null> {
    if (!globalThis.indexedDB) return null;
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "jobId" });
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

export async function loadDownloadState(): Promise<DownloadState | null> {
    const db = await openDb(); if (!db) return null;
    return new Promise((resolve, reject) => {
        const request = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
        request.onsuccess = () => { const rows = request.result as DownloadState[]; db.close(); resolve(rows.length ? rows[rows.length - 1] : null); };
        request.onerror = () => { db.close(); reject(request.error); };
    });
}

export async function saveDownloadState(state: DownloadState): Promise<void> {
    const db = await openDb(); if (!db) return;
    await new Promise<void>((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite"); tx.objectStore(STORE).put(state);
        tx.oncomplete = () => { db.close(); resolve(); }; tx.onerror = () => { db.close(); reject(tx.error); };
    });
}

/** Ask for the parent directory during the user gesture; the job-named child is created after POST. */
export async function choosePackageDirectory(): Promise<FileSystemDirectoryHandle | undefined> {
    if (!window.showDirectoryPicker) return undefined;
    const directory = await window.showDirectoryPicker({ mode: "readwrite" });
    const permission = directory.requestPermission
        ? await directory.requestPermission({ mode: "readwrite" })
        : await directory.queryPermission?.({ mode: "readwrite" });
    if (permission !== "granted") throw new Error("Read/write permission was not granted for the selected destination folder.");
    return directory;
}

async function blobBytes(blob: Blob): Promise<ArrayBuffer> {
    if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
    return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = () => reject(reader.error); reader.readAsArrayBuffer(blob); });
}

async function checksum(blob: Blob): Promise<string> {
    if (!globalThis.crypto?.subtle) throw new Error("This browser cannot verify PDF checksums.");
    const buffer = await blobBytes(blob);
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}

async function validSavedPdf(directory: FileSystemDirectoryHandle, name: string, expectedSize: number, expected: string): Promise<boolean> {
    try {
        const file = await (await directory.getFileHandle(name)).getFile();
        if (file.size !== expectedSize) return false;
        const bytes = new Uint8Array(await blobBytes(file.slice(0, 5)));
        if (new TextDecoder().decode(bytes) !== "%PDF-") return false;
        // This is deliberately a structural, browser-native guard rather than
        // treating a PDF signature as proof that a response is a readable PDF.
        // Native viewers parse the file on open; require a complete PDF trailer
        // before allowing the local-save state to advance.
        const tail = new TextDecoder().decode(new Uint8Array(await blobBytes(file.slice(Math.max(0, file.size - 2048)))));
        if (!tail.includes("%%EOF")) return false;
        return (await checksum(file)).toLowerCase() === expected.toLowerCase();
    }
    catch { return false; }
}

/** A deliberately single-flight client queue. A file is recorded only after a checksum-verified write closes. */
export class SequentialPackageDownloadManager {
    private state: DownloadState;
    private active: Promise<void> | null = null;
    private items = new Map<string, PackageLicence>();
    public onChange?: (state: DownloadState) => void;
    public onError?: (item: PackageLicence, error: Error) => void;

    constructor(state: DownloadState) { this.state = { ...state, queued: [...state.queued], downloaded: [...state.downloaded], failed: [...state.failed], expected: { ...(state.expected ?? {}) } }; }
    snapshot(): DownloadState { return { ...this.state, queued: [...this.state.queued], downloaded: [...this.state.downloaded], failed: [...this.state.failed], expected: { ...this.state.expected } }; }
    private async changed() { await saveDownloadState(this.snapshot()); this.onChange?.(this.snapshot()); }

    enqueue(items: PackageLicence[]) { void this.enqueueAsync(items); }
    private async enqueueAsync(items: PackageLicence[]) {
        items.forEach(item => this.items.set(itemKey(item), item));
        const candidates = items.filter(item => ["server_ready", "completed"].includes(item.status) && item.download_url && item.size && item.sha256)
            .sort((a, b) => String(a.completed_at ?? "").localeCompare(String(b.completed_at ?? "")) || a.licence_number.localeCompare(b.licence_number));
        for (const item of candidates) {
            const key = itemKey(item);
            this.state.expected[key] = { filename: item.filename!, size: Number(item.size), sha256: item.sha256! };
            // Persisted state is not trusted by itself after refresh: only a
            // closed file whose checksum still matches remains downloaded.
            if (this.state.downloaded.includes(key) && this.state.directory && !await validSavedPdf(this.state.directory, item.filename!, Number(item.size), item.sha256!)) this.state.downloaded = this.state.downloaded.filter(id => id !== key);
            if (!this.state.downloaded.includes(key) && !this.state.queued.includes(key) && this.state.downloading !== key) this.state.queued.push(key);
        }
        void this.changed();
        // A restored directory handle can require a new click-based grant. Do
        // not downgrade that case into uncontrolled browser downloads.
        if (this.state.directory && this.state.directoryAuthorized === false) return;
        if (!this.active) this.active = this.drain().finally(() => { this.active = null; if (this.state.queued.length) this.enqueue([]); });
    }

    async authorizeDirectory(): Promise<boolean> {
        if (!this.state.directory?.requestPermission) return !this.state.directory;
        this.state.directoryAuthorized = await this.state.directory.requestPermission({ mode: "readwrite" }) === "granted";
        await this.changed();
        if (this.state.directoryAuthorized) this.enqueue([]);
        return this.state.directoryAuthorized;
    }

    private async drain() {
        while (this.state.queued.length) {
            const key = this.state.queued.shift()!;
            const item = this.items.get(key);
            if (!item || !item.download_url || !item.filename || !item.size || !item.sha256 || this.state.downloaded.includes(key)) continue;
            this.state.downloading = key; await this.changed();
            try {
                await this.download(item);
                this.state.downloaded.push(key); this.state.failed = this.state.failed.filter(id => id !== key);
            } catch (reason) {
                this.state.failed = [...new Set([...this.state.failed, key])];
                this.onError?.(item, reason instanceof Error ? reason : new Error("PDF download failed."));
            } finally { this.state.downloading = null; await this.changed(); }
        }
    }

    private async download(item: PackageLicence) {
        const name = safeFilename(item.filename!);
        if (!this.state.directory) throw new Error("No destination folder is selected. Use the explicit ZIP or individual-download fallback.");
        if (await validSavedPdf(this.state.directory, name, Number(item.size), item.sha256!)) return;
        const response = await api.get(relativeApiUrl(item.download_url!), { responseType: "blob", validateStatus: () => true });
        if (response.status < 200 || response.status >= 300) throw new Error(`PDF download failed (${response.status}).`);
        const contentType = String(response.headers?.["content-type"] ?? "").toLowerCase();
        const blob = response.data instanceof Blob ? response.data : new Blob([response.data]);
        if (!contentType.includes("application/pdf") || !blob.size || blob.size !== Number(item.size)) throw new Error("The downloaded file is not the expected PDF.");
        const signature = new TextDecoder().decode(new Uint8Array(await blobBytes(blob.slice(0, 5))));
        const tail = new TextDecoder().decode(new Uint8Array(await blobBytes(blob.slice(Math.max(0, blob.size - 2048)))));
        if (!signature.startsWith("%PDF-") || !tail.includes("%%EOF") || (await checksum(blob)).toLowerCase() !== item.sha256!.toLowerCase()) throw new Error("PDF verification failed.");
        const handle = await this.state.directory.getFileHandle(name, { create: true });
        const writable = await handle.createWritable();
        try { await writable.write(blob); await writable.close(); } catch (error) { await writable.abort?.(); throw error; }
        if (!await validSavedPdf(this.state.directory, name, Number(item.size), item.sha256!)) {
            throw new Error("The saved PDF could not be reopened and verified.");
        }
    }
}
