import Sidebar from "./Sidebar";
import TopNav from "../components/TopNav";

export default function AdminLayout({children}) {
    return (
        <div className="d-flex">
            <Sidebar/>

            <div className="flex-grow-1">
                <TopNav/>
                <div className="container-fluid p-4">
                    {children}
                </div>
            </div>
        </div>
    );
}
