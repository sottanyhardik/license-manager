import AllotmentAction from '../pages/AllotmentAction';

export default function AllotmentAllocationModal({ show, onHide, allotmentId }) {
    if (!show || !allotmentId) return null;

    return (
        <div
            className="modal show d-block"
            style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050 }}
            onClick={(e) => {
                // Close on backdrop click
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
                            <i className="bi bi-box-arrow-in-down me-2"></i>
                            Allotment Allocation
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
                        <AllotmentAction
                            allotmentId={allotmentId}
                            isModal={true}
                            onClose={onHide}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
