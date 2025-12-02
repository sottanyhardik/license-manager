import TopNav from "../components/TopNav";

export default function AdminLayout({children}) {
    return (
        <div className="d-flex">
            <div className="flex-grow-1">
                <TopNav/>
                <div className="container-fluid">
                    {children}
                </div>
            </div>
        </div>
    );
}
