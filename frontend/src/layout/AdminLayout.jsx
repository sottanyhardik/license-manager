import TopNav from "../components/TopNav";
import {useLocation, useNavigate} from "react-router-dom";
import {useEffect, useState} from "react";

export default function AdminLayout({children}) {
    const location = useLocation();
    const navigate = useNavigate();
    const [isInIframe, setIsInIframe] = useState(false);

    useEffect(() => {
        // Check if the page is loaded in an iframe
        setIsInIframe(window.self !== window.top);
    }, []);

    return (
        <div className="d-flex flex-column" style={{minHeight: "100vh"}}>
            {!isInIframe && <TopNav/>}
            <div className="flex-grow-1" style={{
                backgroundColor: 'var(--background-color)',
                overflowY: 'auto'
            }}>
                <div className="container-fluid" style={{
                    padding: isInIframe ? '1rem 1.5rem' : '2rem 1.5rem',
                    maxWidth: '100%',
                    paddingBottom: isInIframe ? '1rem' : '5rem'
                }}>
                    {children}
                </div>
            </div>
            {!isInIframe && <footer className="bg-white border-top py-3 mt-auto" style={{position: 'sticky', bottom: 0, zIndex: 1000}}>
                <div className="container-fluid">
                    <div className="row align-items-center">
                        <div className="col-md-8">
                            <div className="d-flex gap-2 flex-wrap">
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => navigate('/licenses/create')}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New License
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-info"
                                    onClick={() => navigate('/allotments')}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New Allotment
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-success"
                                    onClick={() => navigate('/bill-of-entries')}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New BOE
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-secondary"
                                    onClick={() => navigate('/reports')}>
                                    <i className="bi bi-file-earmark-text me-1"></i>
                                    View Reports
                                </button>
                            </div>
                        </div>
                        <div className="col-md-4 text-end">
                            <small className="text-muted">
                                Made with <span style={{color: '#dc3545'}}>❤️</span> by Hardik Sottany
                            </small>
                        </div>
                    </div>
                </div>
            </footer>}
        </div>
    );
}
