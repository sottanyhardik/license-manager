export default function Dashboard() {
    return (
        <div className="container mt-4">
            <h2>Dashboard</h2>

            <div className="row mt-4">
                <div className="col-lg-4">
                    <div className="card shadow-sm p-3">
                        <h5>Total Licenses</h5>
                        <h2>120</h2>
                    </div>
                </div>

                <div className="col-lg-4">
                    <div className="card shadow-sm p-3">
                        <h5>Active</h5>
                        <h2 className="text-success">90</h2>
                    </div>
                </div>

                <div className="col-lg-4">
                    <div className="card shadow-sm p-3">
                        <h5>Expired</h5>
                        <h2 className="text-danger">30</h2>
                    </div>
                </div>
            </div>
        </div>
    );
}
