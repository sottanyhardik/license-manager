import TopNav from "../components/TopNav";
import {useLocation, useNavigate} from "react-router-dom";
import {useEffect, useState} from "react";
import {usePageTitle} from "../hooks/usePageTitle";

export default function AdminLayout({children}) {
    const location = useLocation();
    const navigate = useNavigate();
    const [isInIframe, setIsInIframe] = useState(false);
    usePageTitle();

    useEffect(() => {
        // Check if the page is loaded in an iframe
        setIsInIframe(window.self !== window.top);
    }, []);

    return (
        <div className="d-flex flex-column" style={{minHeight: "100vh"}}>
            {!isInIframe && <TopNav/>}
            <main id="main-content" className="flex-grow-1" style={{
                backgroundColor: 'var(--background-color)',
                overflowY: 'auto'
            }}>
                <div className="container-fluid" style={{
                    padding: isInIframe ? '1rem 1.5rem' : '2rem 1.5rem',
                    maxWidth: '100%',
                    paddingBottom: isInIframe ? '1rem' : '90px'
                }}>
                    {/* ARIA live region for form validation announcements */}
                    <div
                        id="form-announcements"
                        role="status"
                        aria-live="polite"
                        aria-atomic="true"
                        className="visually-hidden"
                    ></div>
                    {children}
                </div>
            </main>
            {!isInIframe && <footer className="border-top py-3" style={{
                position: 'fixed',
                bottom: 0,
                left: 0,
                right: 0,
                zIndex: 1000,
                background: 'linear-gradient(to bottom, rgba(248, 249, 250, 0.97), rgba(255, 255, 255, 0.99))',
                backdropFilter: 'blur(10px)',
                boxShadow: '0 -2px 10px rgba(0,0,0,0.05)'
            }}>
                <div className="container-fluid">
                    <div className="row align-items-center">
                        <div className="col-md-8">
                            <div className="d-flex gap-2 flex-wrap">
                                <button
                                    className="btn btn-sm"
                                    onClick={() => navigate('/licenses/create')}
                                    style={{
                                        background: 'var(--primary-gradient)',
                                        color: 'white',
                                        border: 'none',
                                        fontWeight: '500',
                                        padding: '6px 16px'
                                    }}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New License
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={() => navigate('/allotments/create')}
                                    style={{ fontWeight: '500', padding: '6px 16px' }}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New Allotment
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-success"
                                    onClick={() => navigate('/masters/bill-of-entries/create')}
                                    style={{ fontWeight: '500', padding: '6px 16px' }}>
                                    <i className="bi bi-plus-circle me-1"></i>
                                    New BOE
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-secondary"
                                    onClick={() => navigate('/reports/item-pivot')}
                                    style={{ fontWeight: '500', padding: '6px 16px' }}>
                                    <i className="bi bi-file-earmark-text me-1"></i>
                                    View Reports
                                </button>
                            </div>
                        </div>
                        <div className="col-md-4 text-end">
                            <small style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                Made with <span style={{color: 'var(--danger-color)'}}>❤️</span> by Hardik Sottany
                            </small>
                        </div>
                    </div>
                </div>
            </footer>}
        </div>
    );
}
