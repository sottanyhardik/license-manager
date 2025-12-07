import MasterForm from '../pages/masters/MasterForm';

export default function MasterFormModal({ show, onHide, entityName, recordId, mode = 'edit', onSuccess }) {
    if (!show) return null;

    const modeLabel = mode === 'copy' ? 'Copy' : 'Edit';
    const modeIcon = mode === 'copy' ? 'bi-files' : 'bi-pencil-square';
    const entityTitle = entityName === 'allotments' ? 'Allotment' : entityName;

    return (
        <div
            className="modal show d-block"
            style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050 }}
            onClick={(e) => {
                if (e.target === e.currentTarget) {
                    onHide();
                }
            }}
        >
            <div className="modal-dialog modal-fullscreen">
                <div className="modal-content">
                    <div
                        className="modal-header"
                        style={{
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            color: 'white',
                            padding: '1rem 1.5rem',
                            borderBottom: 'none'
                        }}
                    >
                        <h5
                            className="modal-title"
                            style={{
                                fontWeight: '600',
                                fontSize: '1.15rem',
                                letterSpacing: '0.3px'
                            }}
                        >
                            <i className={'bi ' + modeIcon + ' me-2'}></i>
                            {modeLabel} {entityTitle}
                        </h5>
                        <button
                            type="button"
                            className="btn-close btn-close-white"
                            onClick={onHide}
                            aria-label="Close"
                        ></button>
                    </div>
                    <div
                        className="modal-body"
                        style={{
                            padding: 0,
                            overflow: 'auto',
                            height: 'calc(100vh - 65px)',
                            backgroundColor: '#f8f9fa'
                        }}
                    >
                        <MasterForm
                            entityName={entityName}
                            recordId={recordId}
                            isModal={true}
                            onClose={onHide}
                            onSuccess={onSuccess}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
