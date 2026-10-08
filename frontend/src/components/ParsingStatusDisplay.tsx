import { useParsingStatus } from '@/context/ParsingStatusContext';
import Icon from '@/components/Icon';

export default function ParsingStatusDisplay() {
  const { parsingStatus } = useParsingStatus();

  if (!parsingStatus) return null;

  const progress = parsingStatus.totalItems > 0
    ? Math.round((parsingStatus.itemsProcessed / parsingStatus.totalItems) * 100)
    : 0;

  const getStatusColor = () => {
    switch (parsingStatus.status) {
      case 'parsing':
      case 'creating':
        return 'text-blue-600';
      case 'complete':
        return 'text-green-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = () => {
    switch (parsingStatus.status) {
      case 'parsing':
      case 'creating':
        return 'arrow-clockwise';
      case 'complete':
        return 'check-circle-fill';
      case 'error':
        return 'exclamation-circle-fill';
      default:
        return 'clock';
    }
  };

  const getStatusText = () => {
    switch (parsingStatus.status) {
      case 'parsing':
        return `Parsing: ${parsingStatus.itemsProcessed}/${parsingStatus.totalItems} items`;
      case 'creating':
        return `Creating HS codes: ${parsingStatus.hsCodesCreated} created`;
      case 'complete':
        return `✓ Complete: ${parsingStatus.totalItems} items, ${parsingStatus.hsCodesCreated} HS codes created`;
      case 'error':
        return `✗ Error: ${parsingStatus.errorMessage || 'Unknown error'}`;
      default:
        return 'Processing...';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-blue-50 border border-blue-200">
      <Icon
        name={getStatusIcon()}
        className={`size-4 ${getStatusColor()} ${
          (parsingStatus.status === 'parsing' || parsingStatus.status === 'creating') ? 'animate-spin' : ''
        }`}
        aria-hidden="true"
      />
      <div className="flex flex-col gap-0.5">
        <span className={`text-xs font-medium ${getStatusColor()}`}>
          PDF Parsing: {parsingStatus.fileName}
        </span>
        <span className="text-xs text-gray-600">
          {getStatusText()}
        </span>
        {parsingStatus.status === 'parsing' && parsingStatus.totalItems > 0 && (
          <div className="mt-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
