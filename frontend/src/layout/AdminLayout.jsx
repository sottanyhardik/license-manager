import TopNav from "../components/TopNav";

export default function AdminLayout({children}) {
    return (
        <div className="d-flex flex-column" style={{minHeight: "100vh"}}>
            <TopNav/>
            <div className="flex-grow-1" style={{
                backgroundColor: 'var(--background-color)',
                overflowY: 'auto'
            }}>
                <div className="container-fluid" style={{
                    padding: '2rem 1.5rem',
                    maxWidth: '100%'
                }}>
                    {children}
                </div>
            </div>
        </div>
    );
}
