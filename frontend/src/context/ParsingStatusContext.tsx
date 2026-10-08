import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export interface ParsingStatus {
  isActive: boolean;
  fileName: string;
  itemsProcessed: number;
  totalItems: number;
  hsCodesCreated: number;
  status: 'parsing' | 'creating' | 'complete' | 'error';
  errorMessage?: string;
}

interface ParsingStatusContextType {
  parsingStatus: ParsingStatus | null;
  startParsing: (fileName: string, totalItems: number) => void;
  updateProgress: (itemsProcessed: number, hsCodesCreated: number) => void;
  completeParsing: (hsCodesCreated: number) => void;
  errorParsing: (errorMessage: string) => void;
  clearStatus: () => void;
}

const ParsingStatusContext = createContext<ParsingStatusContextType | undefined>(undefined);

export function ParsingStatusProvider({ children }: { children: ReactNode }) {
  const [parsingStatus, setParsingStatus] = useState<ParsingStatus | null>(null);

  const startParsing = useCallback((fileName: string, totalItems: number) => {
    setParsingStatus({
      isActive: true,
      fileName,
      itemsProcessed: 0,
      totalItems,
      hsCodesCreated: 0,
      status: 'parsing',
    });
  }, []);

  const updateProgress = useCallback((itemsProcessed: number, hsCodesCreated: number) => {
    setParsingStatus(prev => prev ? { ...prev, itemsProcessed, hsCodesCreated } : null);
  }, []);

  const completeParsing = useCallback((hsCodesCreated: number) => {
    setParsingStatus(prev => prev ? { ...prev, isActive: false, status: 'complete', hsCodesCreated } : null);
    // Auto-clear after 5 seconds
    setTimeout(() => setParsingStatus(null), 5000);
  }, []);

  const errorParsing = useCallback((errorMessage: string) => {
    setParsingStatus(prev => prev ? { ...prev, isActive: false, status: 'error', errorMessage } : null);
    // Auto-clear after 10 seconds
    setTimeout(() => setParsingStatus(null), 10000);
  }, []);

  const clearStatus = useCallback(() => {
    setParsingStatus(null);
  }, []);

  return (
    <ParsingStatusContext.Provider
      value={{
        parsingStatus,
        startParsing,
        updateProgress,
        completeParsing,
        errorParsing,
        clearStatus,
      }}
    >
      {children}
    </ParsingStatusContext.Provider>
  );
}

export function useParsingStatus() {
  const context = useContext(ParsingStatusContext);
  if (context === undefined) {
    throw new Error('useParsingStatus must be used within ParsingStatusProvider');
  }
  return context;
}
