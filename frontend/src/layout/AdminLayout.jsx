import TopNav from "../components/TopNav";

export default function AdminLayout({children}) {
    return (
        <div className="d-flex">
            <div className="flex-grow-1">
                <TopNav/>
                <div className="container-fluid px-0">
                    {children}
                </div>
            </div>
        </div>
    );
}
