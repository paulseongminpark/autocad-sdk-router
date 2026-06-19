using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

namespace Ariadne.DwgGeometryExtractor;

public sealed class GeometryExtractor
{
    public DwgGeometryDocument Extract(Database db, string? documentName)
    {
        var doc = new DwgGeometryDocument
        {
            Source = new SourceInfo
            {
                DwgName = Path.GetFileName(documentName ?? db.Filename),
                DwgPath = documentName,
                DatabaseFilename = db.Filename,
                Units = db.Insunits.ToString(),
                TileMode = db.TileMode,
            },
        };

        using var tr = db.TransactionManager.StartTransaction();
        var modelSpaceId = SymbolUtilityServices.GetBlockModelSpaceId(db);
        var modelSpace = (BlockTableRecord)tr.GetObject(modelSpaceId, OpenMode.ForRead);

        foreach (ObjectId entityId in modelSpace)
        {
            var entity = tr.GetObject(entityId, OpenMode.ForRead, false) as Entity;
            if (entity == null)
            {
                continue;
            }

            var record = ExtractEntity(entity, tr);
            doc.Entities.Add(record);

            if (!doc.Summary.EntitiesByType.ContainsKey(record.Type))
            {
                doc.Summary.EntitiesByType[record.Type] = 0;
            }
            doc.Summary.EntitiesByType[record.Type]++;

            if (record.Geometry.Kind == "unsupported" || record.ExtractionError != null)
            {
                doc.Summary.UnsupportedGeometryCount++;
            }
            else
            {
                doc.Summary.SupportedGeometryCount++;
            }
        }

        doc.Summary.ModelspaceCount = doc.Entities.Count;
        tr.Commit();
        return doc;
    }

    private static EntityRecord ExtractEntity(Entity entity, Transaction tr)
    {
        var record = new EntityRecord
        {
            Handle = entity.Handle.ToString(),
            ObjectId = entity.ObjectId.ToString(),
            Type = DxfType(entity),
            RuntimeType = entity.GetType().FullName ?? entity.GetType().Name,
            Layer = Safe(() => entity.Layer) ?? "",
            Layout = "Model",
            Linetype = Safe(() => entity.Linetype),
            Visible = Safe(() => entity.Visible),
            BBox = Safe(() => ToBoundingBox(entity.GeometricExtents)),
            XData = ExtractXData(entity),
        };

        var color = Safe(() => entity.Color);
        if (color != null && color.ColorMethod != ColorMethod.None)
        {
            record.ColorIndex = color.ColorIndex;
        }

        try
        {
            record.Geometry = ExtractGeometry(entity, tr);
        }
        catch (System.Exception ex)
        {
            record.Geometry = new GeometryPayload { Kind = "unsupported" };
            record.ExtractionError = ex.Message;
        }

        return record;
    }

    private static GeometryPayload ExtractGeometry(Entity entity, Transaction tr)
    {
        return entity switch
        {
            Line line => new GeometryPayload
            {
                Kind = "line",
                Start = ToPoint(line.StartPoint),
                End = ToPoint(line.EndPoint),
            },
            Polyline polyline => ExtractPolyline(polyline),
            Polyline2d polyline2d => ExtractPolyline2d(polyline2d, tr),
            Polyline3d polyline3d => ExtractPolyline3d(polyline3d, tr),
            Arc arc => new GeometryPayload
            {
                Kind = "arc",
                Center = ToPoint(arc.Center),
                Radius = arc.Radius,
                StartAngle = arc.StartAngle,
                EndAngle = arc.EndAngle,
            },
            Circle circle => new GeometryPayload
            {
                Kind = "circle",
                Center = ToPoint(circle.Center),
                Radius = circle.Radius,
            },
            BlockReference block => ExtractBlockReference(block, tr),
            DBText text => new GeometryPayload
            {
                Kind = "text",
                Position = ToPoint(text.Position),
                Text = text.TextString,
                Height = text.Height,
                Rotation = text.Rotation,
            },
            MText text => new GeometryPayload
            {
                Kind = "mtext",
                Position = ToPoint(text.Location),
                Text = text.Contents,
                Height = text.TextHeight,
                Rotation = text.Rotation,
            },
            Dimension dimension => new GeometryPayload
            {
                Kind = "dimension",
                Position = ToPoint(dimension.TextPosition),
                Text = dimension.DimensionText,
            },
            Hatch hatch => new GeometryPayload
            {
                Kind = "hatch",
                LoopCount = hatch.NumberOfLoops,
            },
            _ => new GeometryPayload { Kind = "unsupported" },
        };
    }

    private static GeometryPayload ExtractPolyline(Polyline polyline)
    {
        var vertices = new List<VertexDto>();
        for (var i = 0; i < polyline.NumberOfVertices; i++)
        {
            vertices.Add(new VertexDto
            {
                Point = ToPoint(polyline.GetPoint3dAt(i)),
                Bulge = polyline.GetBulgeAt(i),
                StartWidth = polyline.GetStartWidthAt(i),
                EndWidth = polyline.GetEndWidthAt(i),
            });
        }

        return new GeometryPayload
        {
            Kind = "polyline",
            Closed = polyline.Closed,
            Vertices = vertices,
        };
    }

    private static GeometryPayload ExtractPolyline2d(Polyline2d polyline, Transaction tr)
    {
        var vertices = new List<VertexDto>();
        foreach (ObjectId vertexId in polyline)
        {
            if (tr.GetObject(vertexId, OpenMode.ForRead, false) is Vertex2d vertex)
            {
                vertices.Add(new VertexDto
                {
                    Point = ToPoint(vertex.Position),
                    Bulge = vertex.Bulge,
                });
            }
        }

        return new GeometryPayload
        {
            Kind = "polyline",
            Closed = polyline.Closed,
            Vertices = vertices,
        };
    }

    private static GeometryPayload ExtractPolyline3d(Polyline3d polyline, Transaction tr)
    {
        var vertices = new List<VertexDto>();
        foreach (ObjectId vertexId in polyline)
        {
            if (tr.GetObject(vertexId, OpenMode.ForRead, false) is PolylineVertex3d vertex)
            {
                vertices.Add(new VertexDto { Point = ToPoint(vertex.Position) });
            }
        }

        return new GeometryPayload
        {
            Kind = "polyline",
            Closed = polyline.Closed,
            Vertices = vertices,
        };
    }

    private static GeometryPayload ExtractBlockReference(BlockReference block, Transaction tr)
    {
        var blockName = BlockTableRecordName(block.BlockTableRecord, tr);
        var effectiveName = blockName;
        if (block.IsDynamicBlock)
        {
            effectiveName = BlockTableRecordName(block.DynamicBlockTableRecord, tr) ?? effectiveName;
        }

        return new GeometryPayload
        {
            Kind = "block_reference",
            Position = ToPoint(block.Position),
            BlockName = blockName,
            EffectiveName = effectiveName,
            Scale = new PointDto
            {
                X = block.ScaleFactors.X,
                Y = block.ScaleFactors.Y,
                Z = block.ScaleFactors.Z,
            },
            Rotation = block.Rotation,
            Transform = MatrixToArray(block.BlockTransform),
            Attributes = ExtractAttributes(block, tr),
        };
    }

    private static List<AttributeDto> ExtractAttributes(BlockReference block, Transaction tr)
    {
        var attributes = new List<AttributeDto>();
        foreach (ObjectId attributeId in block.AttributeCollection)
        {
            if (tr.GetObject(attributeId, OpenMode.ForRead, false) is AttributeReference attribute)
            {
                attributes.Add(new AttributeDto
                {
                    Tag = attribute.Tag,
                    Text = attribute.TextString,
                    Position = ToPoint(attribute.Position),
                });
            }
        }

        return attributes;
    }

    private static string? BlockTableRecordName(ObjectId blockTableRecordId, Transaction tr)
    {
        return Safe(() =>
        {
            var btr = (BlockTableRecord)tr.GetObject(blockTableRecordId, OpenMode.ForRead, false);
            return btr.Name;
        });
    }

    private static List<XDataValue> ExtractXData(Entity entity)
    {
        var values = new List<XDataValue>();
        ResultBuffer? buffer = null;
        try
        {
            buffer = entity.XData;
            if (buffer == null)
            {
                return values;
            }

            foreach (var typedValue in buffer.AsArray())
            {
                values.Add(new XDataValue
                {
                    TypeCode = typedValue.TypeCode,
                    Value = typedValue.Value?.ToString(),
                });
            }
        }
        catch
        {
            return values;
        }
        finally
        {
            buffer?.Dispose();
        }

        return values;
    }

    private static string DxfType(Entity entity)
    {
        return entity switch
        {
            Polyline => "LWPOLYLINE",
            Polyline2d => "POLYLINE",
            Polyline3d => "POLYLINE3D",
            DBText => "TEXT",
            MText => "MTEXT",
            BlockReference => "INSERT",
            _ => entity.GetRXClass()?.DxfName ?? entity.GetType().Name.ToUpperInvariant(),
        };
    }

    private static BoundingBoxDto ToBoundingBox(Extents3d extents)
    {
        return new BoundingBoxDto
        {
            Min = ToPoint(extents.MinPoint),
            Max = ToPoint(extents.MaxPoint),
        };
    }

    private static PointDto ToPoint(Point3d point)
    {
        return new PointDto { X = point.X, Y = point.Y, Z = point.Z };
    }

    private static double[] MatrixToArray(Matrix3d matrix)
    {
        return matrix.ToArray();
    }

    private static T? Safe<T>(Func<T> getter)
    {
        try
        {
            return getter();
        }
        catch
        {
            return default;
        }
    }
}
